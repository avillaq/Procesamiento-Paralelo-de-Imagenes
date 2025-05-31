from flask import Flask, request, jsonify
import cv2
import numpy as np

app = Flask(__name__)

@app.route("/procesar-nodo", methods=["POST"])
def procesar_imagen_nodo():
    archivo_imagen = request.files["img"]
    data = archivo_imagen.read()
    imagen_np = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
    return jsonify({"status": "la imagen fue procesada correctamente"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)