from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/procesar", methods=["POST"])
def procesar_imagen():
    archivo_imagen = request.files["img"]
    data = archivo_imagen.read()
    print(f"Nombre: {archivo_imagen.filename}")
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)