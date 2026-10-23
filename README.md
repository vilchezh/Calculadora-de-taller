# Calculadora de taller — Acero y Escamas

App web (una sola página, sin servidor) para talleres de carpintería y chapa:
arma el **plano de corte** de tableros, cotiza materiales y genera presupuestos.

**Autor:** Acero y Escamas (vilchezh) · https://github.com/vilchezh

## Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | Toda la app (HTML + CSS + JS en un solo archivo, sin dependencias) |
| `cpsat_corte.py` | Solver **exacto** CP-SAT (Google OR-Tools) que acompaña a la app |
| `pedido-corte.json` | Formato de intercance: lo exporta la app, lo lee el solver |

## Pestañas

1. **Plano de corte** — optimizador de despiece 2D (madera y chapa).
2. **Materiales** — cotizador con ítems tablero, barra, consumible y directo.
3. **Presupuestos** — presupuestos a clientes con WhatsApp y PDF.
4. **Calculadora** — con historial.
5. **Diseño 3D** — diseñador paramétrico (ver abajo).

## Diseño 3D

Arma muebles y estructuras en 3D y genera el despiece:

- **Piezas:** tableros de madera (cajas), perfiles estructurales (catálogo
  precargado: cuadrados 20/30/40/50 y rectangulares 40×20 y 60×40, con
  pared, precio y largo de barra editables), chapa plana y chapa plegada.
- **Renderizador 3D propio** (canvas 2D, algoritmo del pintor): sin
  librerías ni CDN, funciona offline. Los caños se ven huecos.
- **Imán:** alinea a ras, centros y apoya en piso **solo mientras
  arrastrás** (captura configurable). La pieza nunca queda atada: se
  separa cuando quieras. «Unir»/«Separar» no existen como ataduras.
- **Regla** (dos puntos → distancia y ΔX/ΔY/ΔZ) y **transportador**
  (tres puntos → ángulo), con captura a esquinas, centros y bordes.
  Las mediciones se dejan fijas como cotas.
- **Telescopía:** interior libre (lado − 2·espesor), sugerencia de qué
  caños entran según holgura (por defecto 1 mm/lado) y botones
  Extender/Cerrar con solape mínimo.
- **Chapa plegada:** plantillas L, U, C, Z y bandeja con desarrollo
  (BA = (π/2)·(r + K·t), BD = 2·(r + t) − BA), conteo de plegados,
  peso, avisos de pestaña mínima y capacidad de plegadora/cizalla.
  Los dobleces a 90°; esquinas de bandeja aproximadas (documentado).
- **Salidas:** madera/chapa → Plano de corte (la plegada manda su
  desarrollo y suma los plegados); perfiles → Cotizador como barras con
  acomodo de cortes por barra descontando el disco (FFD 1D) y conteo de
  uniones a soldar. Piezas enviadas quedan marcadas para no duplicar;
  «Reenviar todo» las rehabilita. Exportar/importar JSON del diseño.
- **Movimiento:** arrastre con mouse en el piso (Shift = subir/bajar),
  posición numérica X/Y/Z, botones de empuje, rotación en saltos de
  15°/45°, vistas rápidas y «Ajustar». En celular: modos Cámara/Mover
  explícitos + controles numéricos.
- ⚠️ **No calcula resistencia estructural** (aviso visible).

Guarda en localStorage con su propia clave (`diseno3d_v1`), sin tocar las
demás. El ejemplo («Cargar ejemplo» desde la pestaña 3D) arma una mesa
con patas de caño 40×40, travesaños 40×20, tapa de madera y bandeja.

## Optimización de corte: cómo funciona

El plano de corte es una solución del **problema de corte de stock** (cutting
stock problem), que es NP-hard. La app lo resuelve en el navegador combinando:

1. **Empaquetado guillotina** con lista de rectángulos libres (los cortes son
   pasantes, cortables en sierra escuadradora, respetando el disco/kerf).
2. **Grilla de heurísticas**: 5 órdenes de piezas × 2 modos de colocación
   (mejor ajuste y **FFD**, primero-en-ajustar de mayor a menor) × 4 reglas
   de orientación; se elige el mejor resultado.
3. **Apuntamiento final (squeeze/LNS)**: re-empaqueta los tableros ya llenos
   para detectar si las piezas entran en un tablero menos. Solo en trabajos
   chicos (≤ 200 piezas, ≤ 10 tableros) para no frenar el navegador.

## Solver exacto CP-SAT (opcional, en tu compu)

Una página estática no puede ejecutar CP-SAT (no hay versión oficial del
solver para navegador). Para saber si tu plano es **provably óptimo** o si
se puede ahorrar un tablero:

```bash
pip install ortools
python cpsat_corte.py pedido-corte.json        # 120 s por defecto
python cpsat_corte.py pedido-corte.json 300    # más tiempo si hay muchas piezas
```

Flujo: en la app, cargá tus piezas → botón **«Exportar JSON»** → corré el
script. El solver resuelve el empaquetado 2D con rotación (respeta la veta)
y te dice el **mínimo número de tableros**. Si la app ya lo logra, el plano
es óptimo en cantidad de tableros.

> Nota: el kerf se aproxima inflando cada pieza (conservador), y las
> posiciones del solver son de referencia (empaquetado libre): el plano
> cortable en la sierra lo sigue dibujando la app.

## Publicar (GitHub Pages)

El repo `vilchezh/Calculadora-de-taller` sirve `index.html` desde la rama
`main` en https://vilchezh.github.io/Calculadora-de-taller/ — subí el
`index.html` actualizado (commit + push) y el cambio sale solo.
