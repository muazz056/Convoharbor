// Enhanced email validation regex (more comprehensive)
const EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

// Password validation regex
// At least 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;

// Common email domains for additional validation
const SUSPICIOUS_DOMAINS = ['10minutemail.com', 'tempmail.org', 'guerrillamail.com', 'mailinator.com'];

// Input sanitization function
const sanitizeInput = (input) => {
  if (typeof input !== 'string') return '';
  return input
    .trim()
    .replace(/[<>]/g, '') // Remove potential HTML tags
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .replace(/on\w+=/gi, ''); // Remove event handlers
};

export const validateEmail = (email) => {
  if (!email) return 'Email is required';
  
  // Sanitize input
  const sanitizedEmail = sanitizeInput(email);
  
  // Check for basic format
  if (!EMAIL_REGEX.test(sanitizedEmail)) {
    return 'Please enter a valid email address';
  }
  
  // Check email length
  if (sanitizedEmail.length > 254) {
    return 'Email address is too long';
  }
  
  // Check for suspicious domains
  const domain = sanitizedEmail.split('@')[1]?.toLowerCase();
  if (SUSPICIOUS_DOMAINS.includes(domain)) {
    return 'Please use a permanent email address';
  }
  
  // Check for multiple @ symbols
  if ((sanitizedEmail.match(/@/g) || []).length !== 1) {
    return 'Email must contain exactly one @ symbol';
  }
  
  // Check local part length (before @)
  const localPart = sanitizedEmail.split('@')[0];
  if (localPart.length > 64) {
    return 'Email username part is too long';
  }
  
  return '';
};

export const validatePassword = (password) => {
  if (!password) return 'Password is required';
  
  // Check minimum length
  if (password.length < 8) return 'Password must be at least 8 characters long';
  
  // Check maximum length
  if (password.length > 128) return 'Password is too long (maximum 128 characters)';
  
  // Check for common patterns
  if (/(.)\1{2,}/.test(password)) {
    return 'Password cannot contain 3 or more consecutive identical characters';
  }
  
  // Check for common weak passwords
  const weakPasswords = ['password', '12345678', 'qwerty123', 'admin123', 'password123'];
  if (weakPasswords.includes(password.toLowerCase())) {
    return 'This password is too common. Please choose a stronger password';
  }
  
  // Check for required character types
  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter';
  }
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter';
  }
  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number';
  }
  if (!/[@$!%*?&]/.test(password)) {
    return 'Password must contain at least one special character (@$!%*?&)';
  }
  
  return '';
};

export const validateConfirmPassword = (password, confirmPassword) => {
  if (!confirmPassword) return 'Please confirm your password';
  if (password !== confirmPassword) return 'Passwords do not match';
  return '';
};

export const validateName = (name, fieldName = 'Name') => {
  if (!name) return `${fieldName} is required`;
  
  // Sanitize input
  const sanitizedName = sanitizeInput(name);
  
  if (sanitizedName.length < 2) return `${fieldName} must be at least 2 characters long`;
  if (sanitizedName.length > 50) return `${fieldName} cannot exceed 50 characters`;
  
  // Allow letters, spaces, hyphens, and common international characters
  if (!/^[a-zA-ZÀ-ÿ\u0100-\u017F\u0180-\u024F\s\-\'\.]+$/.test(sanitizedName)) {
    return `${fieldName} can only contain letters, spaces, hyphens, and apostrophes`;
  }
  
  // Check for multiple consecutive spaces or special characters
  if (/[\s\-\'\.]{2,}/.test(sanitizedName)) {
    return `${fieldName} cannot contain consecutive spaces or special characters`;
  }
  
  // Check for names that are all caps or all lowercase (likely fake)
  if (sanitizedName.length > 3 && (sanitizedName === sanitizedName.toUpperCase() || sanitizedName === sanitizedName.toLowerCase())) {
    return `${fieldName} should be properly capitalized`;
  }
  
  return '';
};

export const validatePhone = (phone) => {
  if (!phone) return ''; // Phone is optional
  
  // Sanitize input
  const sanitizedPhone = sanitizeInput(phone);
  
  // Remove all non-digit characters except + for validation
  const digitsOnly = sanitizedPhone.replace(/[^\d+]/g, '');
  
  // Check minimum length
  if (digitsOnly.length < 10) return 'Phone number must have at least 10 digits';
  
  // Check maximum length
  if (digitsOnly.length > 15) return 'Phone number cannot exceed 15 digits';
  
  // Basic format validation
  if (!/^\+?[\d\s\-\(\)]{10,20}$/.test(sanitizedPhone)) {
    return 'Please enter a valid phone number';
  }
  
  // Check for obviously fake numbers
  if (/(\d)\1{6,}/.test(digitsOnly)) {
    return 'Please enter a valid phone number';
  }
  
  return '';
};

// Password strength calculator
export const getPasswordStrength = (password) => {
  if (!password) return { strength: 0, label: 'Very Weak', color: '#dc3545' };
  
  let score = 0;
  
  // Length score
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (password.length >= 16) score += 1;
  
  // Character type scores
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[@$!%*?&]/.test(password)) score += 1;
  
  // Complexity bonus
  if (/[A-Z].*[a-z].*[0-9].*[@$!%*?&]/.test(password)) score += 1;
  
  // Penalty for common patterns
  if (/(.)\1{2,}/.test(password)) score -= 1;
  if (/123|abc|qwe/i.test(password)) score -= 1;
  
  score = Math.max(0, Math.min(8, score));
  
  const levels = [
    { min: 0, max: 2, label: 'Very Weak', color: '#dc3545' },
    { min: 3, max: 4, label: 'Weak', color: '#fd7e14' },
    { min: 5, max: 6, label: 'Fair', color: '#ffc107' },
    { min: 7, max: 7, label: 'Good', color: '#20c997' },
    { min: 8, max: 8, label: 'Strong', color: '#28a745' }
  ];
  
  const level = levels.find(l => score >= l.min && score <= l.max) || levels[0];
  
  return {
    strength: score,
    label: level.label,
    color: level.color,
    percentage: (score / 8) * 100
  };
};

// Rate limiting helper
export const createRateLimiter = (maxAttempts, windowMs) => {
  const attempts = new Map();
  
  return (key) => {
    const now = Date.now();
    const windowStart = now - windowMs;
    
    // Clean old attempts
    for (const [attemptKey, timestamps] of attempts.entries()) {
      attempts.set(attemptKey, timestamps.filter(time => time > windowStart));
      if (attempts.get(attemptKey).length === 0) {
        attempts.delete(attemptKey);
      }
    }
    
    // Check current attempts
    const currentAttempts = attempts.get(key) || [];
    if (currentAttempts.length >= maxAttempts) {
      const oldestAttempt = Math.min(...currentAttempts);
      const timeLeft = windowMs - (now - oldestAttempt);
      return {
        allowed: false,
        timeLeft: Math.ceil(timeLeft / 1000),
        remaining: 0
      };
    }
    
    // Record this attempt
    currentAttempts.push(now);
    attempts.set(key, currentAttempts);
    
    return {
      allowed: true,
      timeLeft: 0,
      remaining: maxAttempts - currentAttempts.length
    };
  };
};
