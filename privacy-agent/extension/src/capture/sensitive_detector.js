class SensitiveDetector {
  detect(domState) {
    const results = [];
    const text = domState.visible_text || '';
    const upperText = text.toUpperCase();

    const markers = [
      'TOP SECRET', 'SECRET', 'CONFIDENTIAL', 'RESTRICTED', 
      'FOR OFFICIAL USE ONLY', 'CONTROLLED UNCLASSIFIED'
    ];

    for (const marker of markers) {
      if (upperText.includes(marker)) {
        results.push({
          category: 'CLASSIFICATION_MARKER',
          description: `Found marker: ${marker}`,
          elementId: null,
          confidence: 1.0
        });
      }
    }

    if (domState.elements) {
      for (const el of domState.elements) {
        if (el.attributes) {
          const type = (el.attributes.type || '').toLowerCase();
          const name = (el.attributes.name || '').toLowerCase();
          const id = (el.attributes.id || '').toLowerCase();

          if (type === 'password') {
            results.push({
              category: 'PASSWORD_FIELD',
              description: 'Password input field detected',
              elementId: el.id,
              confidence: 1.0
            });
          }

          if (name.includes('cc') || name.includes('card') || id.includes('cc') || id.includes('card')) {
            if (type === 'text' || type === 'number') {
               results.push({
                 category: 'FINANCIAL_FORM',
                 description: 'Potential credit card field detected',
                 elementId: el.id,
                 confidence: 0.8
               });
            }
          }
        }
      }
    }

    return results;
  }
}

export const sensitiveDetector = new SensitiveDetector();
