// FaceDetector using TensorFlow.js and BlazeFace
class FaceDetector {
  constructor() {
    this.model = null;
    this.loading = false;
    this.threshold = 0.75;
  }

  async init() {
    if (this.model) return;
    if (this.loading) {
      while (this.loading) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      return;
    }
    this.loading = true;
    try {
      if (typeof importScripts === 'function') {
        importScripts('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs');
        importScripts('https://cdn.jsdelivr.net/npm/@tensorflow-models/blazeface');
      } else {
        await import('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs');
        await import('https://cdn.jsdelivr.net/npm/@tensorflow-models/blazeface');
      }
      // @ts-ignore
      this.model = await blazeface.load();
    } catch (error) {
      console.warn("Failed to load BlazeFace model. Face detection will be disabled.", error);
    } finally {
      this.loading = false;
    }
  }

  async detect(imageDataUrl) {
    try {
      await this.init();
      if (!this.model) return [];

      const response = await fetch(imageDataUrl);
      const blob = await response.blob();
      const bitmap = await createImageBitmap(blob);

      const offscreen = new OffscreenCanvas(bitmap.width, bitmap.height);
      const ctx = offscreen.getContext('2d');
      ctx.drawImage(bitmap, 0, 0);

      const predictions = await this.model.estimateFaces(offscreen, false);
      const faces = [];

      for (let i = 0; i < predictions.length; i++) {
        const pred = predictions[i];
        if (pred.probability[0] >= this.threshold) {
          const start = pred.topLeft;
          const end = pred.bottomRight;
          faces.push({
            x: start[0],
            y: start[1],
            width: end[0] - start[0],
            height: end[1] - start[1],
            confidence: pred.probability[0]
          });
        }
      }
      return faces;
    } catch (e) {
      console.warn("Face detection error:", e);
      return [];
    }
  }

  async blurFaces(imageDataUrl, faceRegions) {
    if (!faceRegions || faceRegions.length === 0) return imageDataUrl;

    try {
      const response = await fetch(imageDataUrl);
      const blob = await response.blob();
      const bitmap = await createImageBitmap(blob);

      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap, 0, 0);

      for (const face of faceRegions) {
        const blockSize = 10;
        const x = Math.max(0, Math.floor(face.x));
        const y = Math.max(0, Math.floor(face.y));
        const w = Math.min(canvas.width - x, Math.ceil(face.width));
        const h = Math.min(canvas.height - y, Math.ceil(face.height));

        if (w <= 0 || h <= 0) continue;

        const imageData = ctx.getImageData(x, y, w, h);
        const data = imageData.data;

        for (let by = 0; by < h; by += blockSize) {
          for (let bx = 0; bx < w; bx += blockSize) {
            let r = 0, g = 0, b = 0, count = 0;
            
            for (let iy = 0; iy < blockSize && by + iy < h; iy++) {
              for (let ix = 0; ix < blockSize && bx + ix < w; ix++) {
                const idx = ((by + iy) * w + (bx + ix)) * 4;
                r += data[idx];
                g += data[idx + 1];
                b += data[idx + 2];
                count++;
              }
            }

            r = Math.floor(r / count);
            g = Math.floor(g / count);
            b = Math.floor(b / count);

            for (let iy = 0; iy < blockSize && by + iy < h; iy++) {
              for (let ix = 0; ix < blockSize && bx + ix < w; ix++) {
                const idx = ((by + iy) * w + (bx + ix)) * 4;
                data[idx] = r;
                data[idx + 1] = g;
                data[idx + 2] = b;
              }
            }
          }
        }
        ctx.putImageData(imageData, x, y);
      }

      const blobOut = await canvas.convertToBlob({ type: 'image/png' });
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blobOut);
      });
    } catch (e) {
      console.warn("Face blurring error:", e);
      return imageDataUrl;
    }
  }
}

export const faceDetector = new FaceDetector();
