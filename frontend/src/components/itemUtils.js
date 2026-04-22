export const getOriginalAgeInMs = (timeString) => {
  if (!timeString) return 0;
  const parts = timeString.split(' ');
  if (parts.length < 2) return 0;
  
  const number = parseInt(parts[0]);
  if (isNaN(number)) return 0;
  
  let unit;
  if (parts.length >= 3 && parts[2] === 'trước') {
    unit = parts[1] + ' trước';
  } else {
    unit = parts[1];
  }

  switch (unit) {
    case 'giây':
    case 'giây trước':
      return number * 1000;
    case 'phút':
    case 'phút trước':
      return number * 60 * 1000;
    case 'giờ':
    case 'giờ trước':
      return number * 60 * 60 * 1000;
    case 'ngày':
    case 'ngày trước':
      return number * 24 * 60 * 60 * 1000;
    case 'tuần':
    case 'tuần trước':
      return number * 7 * 24 * 60 * 60 * 1000;
    case 'tháng':
    case 'tháng trước':
      return number * 30 * 24 * 60 * 60 * 1000;
    default:
      console.warn(`Unknown time unit: ${unit} in string: ${timeString}`);
      return 0;
  }
};

export const formatAdjustedTime = (listTime) => {
  if (!listTime) return 'Unknown';
  
  try {
    const now = new Date();
    const itemTime = new Date(listTime);
    const diffMs = now.getTime() - itemTime.getTime();
    
    const SECOND_MS = 1000;
    const MINUTE_MS = 60 * 1000;
    const HOUR_MS = 60 * MINUTE_MS;
    const DAY_MS = 24 * HOUR_MS;
    const WEEK_MS = 7 * DAY_MS;
    const MONTH_MS = 30 * DAY_MS;
    
    if (diffMs >= MONTH_MS) {
      const months = Math.round(diffMs / MONTH_MS);
      return `${months} tháng trước`;
    }
    
    if (diffMs >= WEEK_MS) {
      const weeks = Math.round(diffMs / WEEK_MS);
      return `${weeks} tuần trước`;
    }
    
    if (diffMs >= DAY_MS) {
      const days = Math.round(diffMs / DAY_MS);
      return `${days} ngày trước`;
    }
    
    if (diffMs >= HOUR_MS) {
      const hours = Math.round(diffMs / HOUR_MS);
      return `${hours} giờ trước`;
    }
    
    if (diffMs >= MINUTE_MS) {
      const minutes = Math.round(diffMs / MINUTE_MS);
      return `${minutes} phút trước`;
    }

    if (diffMs >= SECOND_MS) {
      const seconds = Math.round(diffMs / SECOND_MS);
      return `${seconds} giây trước`;
    }
    
    return 'Vừa đăng';
  } catch (error) {
    console.error('Error formatting time:', error);
    return 'Unknown';
  }
};

export const formatInputPrice = (value) => {
  if (!value) return '';
  return new Intl.NumberFormat('vi-VN').format(value);
};

export const formatPrice = (price) => {
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND'
  }).format(price).replace('₫', 'đ');
};

export const getEvaluationIcon = (type) => {
  switch (type) {
    case 1: return '🟢';
    case 2: return '🔴';
    default: return '⚪';
  }
};

export const getEvaluationText = (type) => {
  switch (type) {
    case 1: return 'Nên mua';
    case 2: return 'Không mua';
    default: return 'Chưa xử lý';
  }
};