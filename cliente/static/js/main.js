class ImageProcessor {
  constructor() {
    this.fileInput = document.querySelector("#file-upload");
    this.uploadForm = document.querySelector("#upload-form");
    this.uploadArea = document.querySelector("#uploadArea");
    this.previewContainer = document.querySelector("#previewContainer");
    this.uploadProgress = document.querySelector("#uploadProgress");
    this.imagePreview = document.querySelector("#imagePreview");
    this.progressFill = document.querySelector("#progressFill");
    this.progressText = document.querySelector("#progressText");
    this.progressPercentage = document.querySelector("#progressPercentage");
    this.previewImg = document.querySelector("#previewImg");
    this.fileName = document.querySelector("#fileName");
    this.fileSize = document.querySelector("#fileSize");
    this.fileDimensions = document.querySelector("#fileDimensions");
    this.fileType = document.querySelector("#fileType");
    this.processBtn = document.querySelector("#processBtn");
    this.uploadStatus = document.querySelector(".upload-status");
    this.imageOverlay = document.querySelector(".image-overlay");

    this.selectedFile = null;
    this.originalPath = null;
    this.finalPath = null;

    this.initEventListeners();
  }

  initEventListeners() {
    this.fileInput.addEventListener("change", (e) => this.handleFileSelect(e));

    this.uploadArea.addEventListener("dragover", (e) => this.handleDragOver(e));
    this.uploadArea.addEventListener("dragleave", (e) => this.handleDragLeave(e));
    this.uploadArea.addEventListener("drop", (e) => this.handleDrop(e));

    this.uploadArea.addEventListener("click", (e) => {
      if (!e.target.closest(".custom-file-upload")) {
        this.fileInput.click();
      }
    });

    if (this.uploadForm) {
      this.uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (this.selectedFile) {
          await this.startProcessing();
        }
      });
    }
  }

  handleDragOver(e) {
    e.preventDefault();
    this.uploadArea.classList.add("dragover");
  }

  handleDragLeave(e) {
    e.preventDefault();
    this.uploadArea.classList.remove("dragover");
  }

  handleDrop(e) {
    e.preventDefault();
    this.uploadArea.classList.remove("dragover");

    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type.startsWith("image/")) {
      this.fileInput.files = files;
      this.processFile(files[0]);
    }
  }

  handleFileSelect(e) {
    const file = e.target.files[0];
    if (file && file.type.startsWith("image/")) {
      this.processFile(file);
    }
  }

  processFile(file) {
    this.selectedFile = file;
    this.uploadArea.classList.add("file-selected");
    this.previewContainer.classList.add("show");
    this.displayFileInfo(file);
    this.createImagePreview(file);

    // Se oculta la barra de progreso
    this.uploadProgress.style.opacity = "0";
    this.uploadProgress.style.transform = "translateY(10px)";

    this.imagePreview.classList.add("show");

    // boton para procesar
    this.enableProcessButton();
  }

  displayFileInfo(file) {
    this.fileName.textContent = file.name;

    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    this.fileSize.textContent = `${sizeInMB} MB`;

    const fileExtension = file.name.split(".").pop().toUpperCase();
    this.fileType.textContent = fileExtension;
  }

  createImagePreview(file) {
    const reader = new FileReader();

    reader.onload = (e) => {
      this.previewImg.src = e.target.result;

      this.previewImg.onload = () => {
        const img = new Image();
        img.onload = () => {
          this.fileDimensions.textContent = `${img.width} x ${img.height}`;
        };
        img.src = e.target.result;
      };
    };

    reader.readAsDataURL(file);
  }

  enableProcessButton() {
    this.processBtn.disabled = false;
    this.processBtn.querySelector(".btn-text").textContent = "Procesar imagen";
  }

  async startProcessing() {
    const btnText = this.processBtn.querySelector(".btn-text");
    const btnLoader = this.processBtn.querySelector(".btn-loader");

    btnText.textContent = "Procesando...";
    btnLoader.classList.add("show");
    this.processBtn.disabled = true;

    // barra de progreso
    this.uploadProgress.style.opacity = "1";
    this.uploadProgress.style.transform = "translateY(0)";

    // Reiniciar barra de progreso
    this.progressFill.style.width = "0%";
    this.progressPercentage.textContent = "0%";
    this.progressText.textContent = "Subiendo imagen...";

    // Crear FormData para enviar
    const formData = new FormData();
    formData.append("img", this.selectedFile);

    try {
      this.simulateUploadProgress();

      // Realizar la peticion
      const response = await fetch("/procesar", {
        method: "POST",
        body: formData
      });

      // Detener simulacion de subida
      this.stopSimulation = true;

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error);
      }

      // Simular la segunda fase de procesamiento
      this.simulateProcessingProgress();

      // Procesar la respuesta JSON
      const data = await response.json();
      
      // Completar la barra a 100%
      this.updateProgress(100);

      // Almacenar las rutas de las imagenes
      this.originalPath = data.original;
      this.finalPath = data.final;

      // Completar la animacion
      this.completeUpload();

      // Redirigir a la pagina de resultados
      setTimeout(() => {
        window.location.href = `resultado?original=${encodeURIComponent(data.original)}&final=${encodeURIComponent(data.final)}`;
      }, 1500);
      
    } catch (error) {
      console.error("Error en el procesamiento:", error);
      this.stopSimulation = true;
      this.updateProgress(0);
      this.progressText.textContent = error;
      btnText.textContent = "Reintentar";
      btnLoader.classList.remove("show");
      this.processBtn.disabled = false;
    }
  }

  simulateUploadProgress() {
    this.stopSimulation = false;
    let progress = 0;
    
    const simulateUpload = () => {
      if (this.stopSimulation || progress >= 50) return;
      
      progress += (50 - progress) * 0.1;
      
      if (progress > 48) progress = 50;
      
      this.updateProgress(progress);
      
      if (progress >= 50) {
        this.progressText.textContent = "Procesando en el servidor...";
      } else {
        requestAnimationFrame(simulateUpload);
      }
    };
    
    requestAnimationFrame(simulateUpload);
  }

  simulateProcessingProgress() {
    this.stopSimulation = false;
    let progress = 50;
    
    const simulateProcessing = () => {
      if (this.stopSimulation || progress >= 95) return;
      
      progress += 1;
      this.updateProgress(progress);
      
      if (progress < 95) {
        setTimeout(simulateProcessing, 100);
      }
    };
    
    simulateProcessing();
  }

  updateProgress(progress) {
    this.progressFill.style.width = `${progress}%`;
    this.progressPercentage.textContent = `${Math.round(progress)}%`;

    this.progressPercentage.style.animation = "none";
    this.progressPercentage.offsetHeight;
    this.progressPercentage.style.animation = "numberPulse 0.3s ease";

    if (progress < 30) {
      this.progressText.textContent = "Subiendo imagen...";
    } else if (progress < 50) {
      this.progressText.textContent = "Preparando para procesamiento...";
    } else if (progress < 85) {
      this.progressText.textContent = "Procesando en servidor remoto...";
    } else if (progress < 100) {
      this.progressText.textContent = "Recibiendo resultado...";
    } else {
      this.progressText.textContent = "¡Completado!";
    }
  }

  completeUpload() {
    setTimeout(() => {
      this.uploadStatus.classList.add("show");
    }, 500);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new ImageProcessor();
});