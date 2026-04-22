import React from 'react';
import FilterDropdown from './FilterDropdown';
import { CATEGORIES, PROVINCES } from './itemConstants';
import { formatInputPrice } from './itemUtils';

const ItemFilters = ({ filters, setFilters, onOpenBulkEvaluate, aiPendingCount }) => {
  const handleFilterChange = (name, value) => {
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSortChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handlePriceInputChange = (e) => {
    const { name, value } = e.target;
    const numericValue = value.replace(/\D/g, '');
    setFilters(prev => ({ ...prev, [name]: numericValue }));
  };

  return (
    <div className="filters">
      <div className="filter-group sort-group">
        <select name="sortBy" value={filters.sortBy} onChange={handleSortChange} className="sort-filter">
          <option value="newest">Tin mới trước</option>
          <option value="price-high">Giá cao trước</option>
          <option value="price-low">Giá thấp trước</option>
          <option value="roi-high">ROI cao trước</option>
        </select>
      </div>

      <div className="filter-group type-group">
        <select 
          name="evaluatedType" 
          value={filters.evaluatedType === '' ? '' : filters.evaluatedType} 
          onChange={(e) => {
            const val = e.target.value === '' ? '' : Number(e.target.value);
            handleFilterChange('evaluatedType', val);
          }} 
          className="sort-filter"
        >
          <option value="">Tất cả (ẩn loại 2)</option>
          <option value={1}>Type 1 (Kèo thơm)</option>
          <option value={2}>Type 2 (Bỏ qua)</option>
          <option value={0}>Chưa đánh giá</option>
        </select>
      </div>

      <div className="id-search-container">
        <input
          type="text"
          name="itemIds"
          placeholder="Tìm theo ID (123, 456...)"
          defaultValue={filters.itemIds}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleFilterChange('itemIds', e.target.value);
            }
          }}
          onBlur={(e) => handleFilterChange('itemIds', e.target.value)}
          className="id-search-input"
        />
        <button 
          className="reset-filters-btn" 
          onClick={() => setFilters({
            category: '',
            province: '',
            minPrice: '',
            maxPrice: '',
            sortBy: 'newest',
            evaluatedType: 1,
            marketplace: '',
            page: 1,
            itemIds: '',
            is_evaluated: false
          })}
          title="Xóa bộ lọc"
        >
          ↺
        </button>
      </div>

      <div className="filter-group">
        <FilterDropdown
          label="Danh mục"
          options={{ '': 'Tất cả danh mục', ...CATEGORIES }}
          selectedOptions={filters.category}
          onChange={(value) => handleFilterChange('category', value)}
          placeholder="Chọn danh mục"
          isMultiSelect={false}
        />
      </div>

      <div className="filter-group">
        <FilterDropdown
          label="Tỉnh/Thành phố"
          options={{ '': 'Toàn quốc', ...PROVINCES }}
          selectedOptions={filters.province}
          onChange={(value) => handleFilterChange('province', value)}
          placeholder="Chọn tỉnh/thành"
          isMultiSelect={false}
        />
      </div>

      <div className="marketplace-filter">
        <label className="marketplace-checkbox-label">
          <input
            type="checkbox"
            checked={filters.marketplace === 'marketplace'}
            onChange={(e) => handleFilterChange('marketplace', e.target.checked ? 'marketplace' : '')}
            className="marketplace-checkbox"
          />
          <span>📢 Đã đăng Facebook</span>
        </label>
      </div>

      <input
        type="text"
        name="minPrice"
        placeholder="Giá thấp nhất"
        value={formatInputPrice(filters.minPrice)}
        onChange={handlePriceInputChange}
      />
      <input
        type="text"
        name="maxPrice"
        placeholder="Giá cao nhất"
        value={formatInputPrice(filters.maxPrice)}
        onChange={handlePriceInputChange}
      />

      <button 
        className="bulk-evaluate-btn"
        onClick={onOpenBulkEvaluate}
      >
        Insert Eval
      </button>

      {aiPendingCount !== undefined && (
        <div 
          className="ai-pending-badge" 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            backgroundColor: '#e0f7fa', 
            color: '#006064', 
            padding: '8px 12px', 
            borderRadius: '6px', 
            fontWeight: '600',
            marginLeft: 'auto',
            border: '1px solid #b2ebf2',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            gap: '6px'
          }} 
          title="Số lượng tin đang chờ AI đánh giá"
        >
          <span style={{ fontSize: '16px' }}>🤖</span>
          <span>Chờ AI đánh giá: {aiPendingCount}</span>
        </div>
      )}
    </div>
  );
};

export default ItemFilters;
