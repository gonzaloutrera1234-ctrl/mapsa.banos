import threading
import time

from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# Si un baño no avisa en este tiempo, se muestra "SIN CONEXIÓN".
# El ESP32 avisa cada 30 s, asi que 90 s tolera 2 avisos perdidos.
TIMEOUT_SIN_CONEXION = 90

ESTADOS_VALIDOS = ("LIBRE", "OCUPADO")

lock = threading.Lock()

banos = {
    i: {
        "estado": None,
        "visto": None,      # time.monotonic() del ultimo aviso
        "rssi": None,
        "firmware": None,
        "uptime": None,
    }
    for i in (1, 2, 3)
}


def segundos_desde_ultimo_aviso(bano):
    if bano["visto"] is None:
        return None
    return time.monotonic() - bano["visto"]


def estado_visible(bano):
    segundos = segundos_desde_ultimo_aviso(bano)

    if segundos is None or segundos > TIMEOUT_SIN_CONEXION:
        return "SIN CONEXIÓN"

    return bano["estado"]


@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/api/test")
def test():
    return jsonify({
        "servidor": "MAPSA Baños",
        "estado": "FUNCIONANDO"
    })


# Mismo formato que antes: {"bano1": "LIBRE", ...}
@app.route("/api/banos", methods=["GET"])
def obtener_banos():
    with lock:
        return jsonify({
            f"bano{i}": estado_visible(b) for i, b in banos.items()
        })


# Informacion de diagnostico de cada ESP32.
@app.route("/api/banos/detalle", methods=["GET"])
def obtener_detalle():
    with lock:
        resultado = {}

        for i, b in banos.items():
            segundos = segundos_desde_ultimo_aviso(b)

            resultado[f"bano{i}"] = {
                "estado": estado_visible(b),
                "segundos_desde_ultimo_aviso":
                    None if segundos is None else round(segundos),
                "rssi": b["rssi"],
                "firmware": b["firmware"],
                "uptime_segundos": b["uptime"],
            }

        return jsonify(resultado)


@app.route("/api/banos/<int:bano>", methods=["POST"])
def actualizar_bano(bano):

    if bano not in banos:
        return jsonify({"error": "Baño no válido"}), 400

    datos = request.get_json(silent=True)

    if not datos or "estado" not in datos:
        return jsonify({"error": "Falta el estado"}), 400

    estado = datos["estado"]

    if estado not in ESTADOS_VALIDOS:
        return jsonify({
            "error": "Estado no válido. Use LIBRE u OCUPADO"
        }), 400

    with lock:
        banos[bano]["estado"] = estado
        banos[bano]["visto"] = time.monotonic()
        banos[bano]["rssi"] = datos.get("rssi")
        banos[bano]["firmware"] = datos.get("firmware")
        banos[bano]["uptime"] = datos.get("uptime")

    return jsonify({
        "mensaje": "Estado actualizado",
        "bano": bano,
        "estado": estado
    })


if __name__ == "__main__":
    # debug=False: con debug=True queda expuesto el depurador de Werkzeug,
    # que permite ejecutar codigo desde la red.
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
