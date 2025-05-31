from flask import Flask, request, jsonify, send_file
import io
import cv2
import numpy as np

app = Flask(__name__)

@app.route("/procesar-nodo", methods=["POST"])
def procesar_imagen_nodo():
    archivo_imagen = request.files["img"]
    data = archivo_imagen.read()
    imagen_np = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
    
    # Se puede realizar otro procesamiento pero por el momento solo se convierte a escala de grises
    img_gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, buf = cv2.imencode(".png", img_gris)
    resultado_bytes = buf.tobytes()

    return send_file(
        io.BytesIO(resultado_bytes),
        mimetype="image/png",
        as_attachment=False
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)