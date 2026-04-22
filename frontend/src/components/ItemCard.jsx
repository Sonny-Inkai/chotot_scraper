import React from 'react';
import { formatPrice, formatAdjustedTime, getEvaluationIcon, getEvaluationText } from './itemUtils';

const ItemCard = ({ item, isSelected, onCheckboxChange }) => {
  const renderSpecs = (item) => {
    const specs = [];
    if (item.params) {
      for (const param of item.params) {
        specs.push(
          <span key={param.id} className="spec-item">
            {param.label}: {param.value}
          </span>
        );
      }
    }
    return specs;
  };

  return (
    <li className="item-card">
      <div className="item-content">
        <div className="top-right-controls">
          <div className="evaluation-display">
            <div 
              className="evaluation-icon"
              title={item.evaluated?.type ? 
                `${item.evaluated.note}${item.evaluated.type === 1 ? 
                  `\nBuy: ${formatPrice(item.evaluated.buy_price || 0)}` +
                  `\nSell: ${formatPrice(item.evaluated.sell_price || 0)}` +
                  `\nROI: ${item.evaluated.roi}%` : 
                  ''}`
                : ''}
            >
              {getEvaluationIcon(item.evaluated?.type || 0)}
            </div>
            <div 
              className="evaluation-text"
            >
              {getEvaluationText(item.evaluated?.type || 0)}
            </div>
          </div>
          <input
            type="checkbox"
            className="item-checkbox"
            checked={isSelected}
            onChange={() => onCheckboxChange(item._id)}
          />
        </div>
        
        <a href={`https://www.chotot.com/${item._id}.htm`} target="_blank" rel="noopener noreferrer" className="item-image-link">
          <div className="item-image">
            <img src={item.image} alt={item.subject} />
          </div>
        </a>
        
        <div className="item-details">
          <h3>{item.subject}</h3>
          <p className="id">{item._id}</p>
          <p className="price">{formatPrice(item.price)}</p>
          <p className="location">{item.area_name}, {item.region_name}</p>
          <p className="description">{item.body}</p>
          <p className="note">{item.evaluated?.note}</p>
          <div className="specs">
            {renderSpecs(item)}
          </div>
          <div className="user-info">
            <img src={item.avatar} alt={item.account_name} className="user-avatar" />
            <span>{item.account_name}</span>
          </div>
        </div>
      </div>
      <span className="update-time">{formatAdjustedTime(item.list_time)}</span>
    </li>
  );
};

export default ItemCard;