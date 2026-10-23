#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cpsat_corte.py — Solver EXACTO de planos de corte con CP-SAT (Google OR-Tools).

La Calculadora de taller es una página estática: las heurísticas de corte
corren en el navegador y no pueden ejecutar un solver exacto pesado como
CP-SAT. Este script es su compañero de escritorio: toma el archivo
"pedido-corte.json" que la app exporta con el botón «Exportar JSON» y
resuelve el mismo problema de forma EXACTA, encontrando el mínimo número
de tableros (o el mejor valor dentro del límite de tiempo).

Uso:
    pip install ortools
    python cpsat_corte.py pedido-corte.json [segundos]

    - pedido-corte.json : el archivo que descarga la app (por defecto ese nombre)
    - segundos          : límite de tiempo del solver (por defecto 120)

Qué resuelve:
    - Empaquetado 2D de rectángulos en tableros de tamaño fijo.
    - Rotación opcional de piezas (respeta la «veta»: piezas con grain=true
      no se rotan).
    - Objetivo: minimizar la cantidad de tableros usados.

Cómo interpretarlo:
    - Si dice OPTIMAL con N tableros y la app usó N: el plano de la app ya
      es el mejor posible en cantidad de tableros (no se puede con menos).
    - Si el solver encuentra menos tableros que la app: valen la pena los
      recortes de guillotina que hagan falta para lograr ese ahorro.
    - El disco de sierra (kerf) se aproxima inflando cada pieza en kerf mm
      por lado, así que el resultado es un poco conservador.

Las posiciones que imprime son de referencia (empaquetado libre): el armado
final de los cortes de guillotina seguís haciéndolo en la app, que dibuja
el plano cortable en la sierra.
"""

import json
import math
import sys

from ortools.sat.python import cp_model


def load_job(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prepare(job):
    """Devuelve (BL, BW, kerf, piezas) con medidas útiles y enteras."""
    trim = int(job.get("cut", {}).get("trim", 0) or 0)
    BL = int(job["board"]["length"]) - 2 * trim
    BW = int(job["board"]["width"]) - 2 * trim
    kerf = int(job.get("cut", {}).get("kerf", 0) or 0)
    rotate = bool(job.get("cut", {}).get("rotate", True))

    pieces = []          # (nombre, L, W, permite_rotar) — medidas ya con kerf
    display = []         # medidas reales para mostrar
    for p in job.get("pieces", []):
        l = int(p.get("l", 0) or 0)
        w = int(p.get("w", 0) or 0)
        qty = int(p.get("qty", 1) or 1)
        if l <= 0 or w <= 0:
            continue
        can_rot = rotate and not bool(p.get("grain", False))
        fits = (l <= BL and w <= BW) or (can_rot and w <= BL and l <= BW)
        if not fits:
            print(f"  ! {p.get('name', 'pieza')} {l}x{w} mm no entra en el tablero: se ignora")
            continue
        for _ in range(qty):
            pieces.append((p.get("name", "pieza"), l + kerf, w + kerf, can_rot))
            display.append((p.get("name", "pieza"), l, w, can_rot))
    return BL, BW, kerf, pieces, display


def build_and_solve(BL, BW, pieces, max_boards, time_limit):
    """Modelo 2D de bin packing con CP-SAT. Devuelve (solver, estado, datos)."""
    model = cp_model.CpModel()
    nb = max_boards

    used = [model.NewBoolVar(f"used_{b}") for b in range(nb)]
    pres = {}
    xs, ys = {}, {}
    orients = {}                      # (i, b) -> (o0, o1) o None si no rota
    ix = [[] for _ in range(nb)]      # intervalos en X, por tablero
    iy = [[] for _ in range(nb)]      # intervalos en Y, por tablero

    for i, (name, L, W, can_rot) in enumerate(pieces):
        for b in range(nb):
            p_ib = model.NewBoolVar(f"pres_{i}_{b}")
            pres[i, b] = p_ib
            model.AddImplication(p_ib, used[b])

            if can_rot:
                x = model.NewIntVar(0, max(0, BL - min(L, W)), f"x_{i}_{b}")
                y = model.NewIntVar(0, max(0, BW - min(L, W)), f"y_{i}_{b}")
                o0 = model.NewBoolVar(f"h_{i}_{b}")   # L a lo largo
                o1 = model.NewBoolVar(f"v_{i}_{b}")   # L a lo ancho (rotada)
                model.Add(o0 + o1 == p_ib)
                model.Add(x + L <= BL).OnlyEnforceIf(o0)
                model.Add(y + W <= BW).OnlyEnforceIf(o0)
                model.Add(x + W <= BL).OnlyEnforceIf(o1)
                model.Add(y + L <= BW).OnlyEnforceIf(o1)
                ix[b].append(model.NewOptionalIntervalVar(x, L, x + L, o0, f"ix_{i}_{b}"))
                iy[b].append(model.NewOptionalIntervalVar(y, W, y + W, o0, f"iy_{i}_{b}"))
                ix[b].append(model.NewOptionalIntervalVar(x, W, x + W, o1, f"jx_{i}_{b}"))
                iy[b].append(model.NewOptionalIntervalVar(y, L, y + L, o1, f"jy_{i}_{b}"))
                orients[i, b] = (o0, o1)
            else:
                x = model.NewIntVar(0, max(0, BL - L), f"x_{i}_{b}")
                y = model.NewIntVar(0, max(0, BW - W), f"y_{i}_{b}")
                ix[b].append(model.NewOptionalIntervalVar(x, L, x + L, p_ib, f"ix_{i}_{b}"))
                iy[b].append(model.NewOptionalIntervalVar(y, W, y + W, p_ib, f"iy_{i}_{b}"))
                orients[i, b] = None
            xs[i, b] = x
            ys[i, b] = y

        model.Add(sum(pres[i, b] for b in range(nb)) == 1)   # cada pieza, un tablero

    for b in range(nb):
        if ix[b]:
            model.AddNoOverlap2D(ix[b], iy[b])      # rectángulos (X, Y) sin superponerse

    model.Minimize(sum(used))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    return solver, status, (pres, xs, ys, orients, used)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pedido-corte.json"
    time_limit = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0

    job = load_job(path)
    BL, BW, kerf, pieces, display = prepare(job)
    if not pieces:
        print("No hay piezas válidas para resolver.")
        return
    print(f"Tablero útil: {BL} x {BW} mm · kerf {kerf} mm · {len(pieces)} piezas")

    area_lb = max(1, math.ceil(sum(L * W for _, L, W, _ in pieces) / (BL * BW)))
    app_boards = int(job.get("app", {}).get("boards") or 0)
    print(f"Límite inferior por área: {area_lb} tablero(s)")
    if app_boards:
        print(f"Plano de la app: {app_boards} tablero(s)")

    # Arranca desde el valor de la app (es factible) o desde el límite de área.
    nb = max(1, app_boards if app_boards else area_lb)
    for intento in range(6):
        print(f"Probando con {nb} tablero(s)…")
        solver, status, data = build_and_solve(BL, BW, pieces, nb, time_limit)
        name = solver.StatusName(status)
        if status == cp_model.INFEASIBLE:
            nb += 1
            continue
        break

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Sin solución: {name}. Probá con más tiempo (python cpsat_corte.py {path} 300).")
        return

    pres, xs, ys, orients, used = data
    boards_used = sum(1 for u in used if solver.Value(u) == 1)
    print(f"\nEstado: {name} · Tableros necesarios: {boards_used}")

    if app_boards:
        if boards_used < app_boards:
            print(f"✅ El solver encontró un plan con {app_boards - boards_used} tablero(s) menos que la app.")
        else:
            print("✅ La app ya usa la mínima cantidad de tableros posible.")

    board_area = BL * BW
    per_board = {}
    for i, (name, L, W, can_rot) in enumerate(pieces):
        for b in range(nb):
            if solver.Value(pres[i, b]) == 1:
                x = solver.Value(xs[i, b])
                y = solver.Value(ys[i, b])
                rot = False
                if can_rot and orients[i, b]:
                    rot = solver.Value(orients[i, b][1]) == 1
                per_board.setdefault(b, []).append((x, y, rot, display[i]))
                break

    used_area = 0
    for b in sorted(per_board):
        items = per_board[b]
        print(f"\nTablero {b + 1}:")
        for x, y, rot, (name, l, w, _) in sorted(items, key=lambda t: (t[1], t[0])):
            used_area += l * w
            orient = " (rotada)" if rot else ""
            print(f"  {name}: {l} x {w} mm en x={x}, y={y}{orient}")

    consumed = boards_used * board_area
    if consumed:
        print(f"\nAprovechado: {used_area / consumed * 100:.1f} % "
              f"({used_area / 1e6:.3f} m² de {consumed / 1e6:.3f} m²)")


if __name__ == "__main__":
    main()
