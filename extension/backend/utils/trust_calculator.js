// Calculate overall trust score
export function calculateTrustScore(pillars) {
  const { information, media, bias } = pillars;
  
  // Weighted average
  const weights = {
    information: 0.4,
    media: 0.3,
    bias: 0.3
  };
  
  const score = 
    (information.score * weights.information) +
    (media.score * weights.media) +
    (bias.score * weights.bias);
  
  return Math.round(score);
}

// Determine verdict
export function getVerdict(score) {
  if (score >= 80) return 'HIGH TRUST';
  if (score >= 50) return 'MODERATE TRUST';
  return 'LOW TRUST';
}

// Calculate information trust
export function calculateInformationTrust(data) {
  let score = 100;
  
  // Deduct for unverified facts
  if (data.fact_check?.status === 'unverified') score -= 20;
  
  // Deduct for hallucinations
  if (data.hallucination?.detected) score -= 30;
  
  // Deduct for low source credibility
  if (data.sources?.credibility === 'low') score -= 25;
  
  return Math.max(0, score);
}

// Calculate media trust
export function calculateMediaTrust(data) {
  let score = 100;
  
  // Deduct for deepfakes
  if (data.images?.deepfakes_detected > 0) score -= 40;
  
  // Deduct for inauthentic videos
  if (data.videos && !data.videos.authentic) score -= 35;
  
  return Math.max(0, score);
}

// Calculate bias trust
export function calculateBiasTrust(data) {
  let score = 100;
  
  // Deduct for language bias
  if (data.language_bias?.detected) {
    const levelPenalty = {
      low: 10,
      moderate: 25,
      high: 40
    };
    score -= levelPenalty[data.language_bias.level] || 25;
  }
  
  // Deduct for emotional manipulation
  if (data.emotional_manipulation?.detected) score -= 20;
  
  return Math.max(0, score);
}