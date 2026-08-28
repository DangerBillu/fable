import { faceDetector } from './face_detector.js';
import { sensitiveDetector } from './sensitive_detector.js';

class ScreenAnalyzer {
  async analyze(screenshotDataUrl, domState) {
    const startMs = Date.now();
    
    let redactedScreenshot = screenshotDataUrl;
    let faceRegions = [];
    let sensitiveRegions = [];
    let facesDetected = 0;
    let facesBlurred = 0;
    let sensitiveRegionsFound = 0;

    try {
      sensitiveRegions = sensitiveDetector.detect(domState);
      sensitiveRegionsFound = sensitiveRegions.length;

      faceRegions = await faceDetector.detect(screenshotDataUrl);
      facesDetected = faceRegions.length;

      if (facesDetected > 0) {
        redactedScreenshot = await faceDetector.blurFaces(screenshotDataUrl, faceRegions);
        facesBlurred = facesDetected;
      }
    } catch (e) {
      console.warn("Screen analyzer error:", e);
    }

    const processingTimeMs = Date.now() - startMs;

    return {
      originalScreenshot: screenshotDataUrl,
      redactedScreenshot,
      faceRegions,
      sensitiveRegions,
      stats: {
        facesDetected,
        facesBlurred,
        sensitiveRegionsFound,
        processingTimeMs
      }
    };
  }
}

export const screenAnalyzer = new ScreenAnalyzer();
