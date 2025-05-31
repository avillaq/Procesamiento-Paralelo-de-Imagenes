from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/procesar", methods=["POST"])
def procesar_imagen():
    print("Prueba")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)