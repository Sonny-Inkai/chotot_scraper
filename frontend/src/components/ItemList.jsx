import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Pagination from './Pagination';
import ItemFilters from './ItemFilters';
import ItemActions from './ItemActions';
import ItemCard from './ItemCard';
import { BulkEvaluationModal } from './EvaluationModals';
import '../styles/ItemList.css';

const ItemList = () => {
  const queryClient = useQueryClient();

  const [selectedItems, setSelectedItems] = useState(new Set());
  const [filters, setFilters] = useState({
    category: '',
    province: '',
    minPrice: '',
    maxPrice: '',
    sortBy: 'newest',
    evaluatedType: 1,
    marketplace: '',
    page: 1,
    itemIds: '',
    is_evaluated: true
  });
  const [bulkEvaluationState, setBulkEvaluationState] = useState({
    isOpen: false,
    jsonInput: '',
    error: null
  });

  const { data: pendingData } = useQuery({
    queryKey: ['aiPendingCount'],
    queryFn: async () => {
      const response = await axios.get(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/ai-pending-count`);
      return response.data;
    },
    refetchInterval: 30000, // Tự động cập nhật mỗi 30s
  });
  const aiPendingCount = pendingData?.count || 0;

  const { data } = useQuery({
    queryKey: ['items', filters],
    queryFn: async () => {
      const params = { ...filters };
      
      if (params.itemIds) {
        params.itemIds = params.itemIds.split(',')
          .map(id => id.trim())
          .filter(id => id !== '')
          .join(',');
      }
      
      Object.keys(params).forEach(key => {
        if (params[key] === '') {
          delete params[key];
        }
      });
      
      const response = await axios.get(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/items`, { params });
      return response.data;
    },
  });

  const items = data?.items || [];
  const pagination = data?.pagination || {
    total: 0,
    totalPages: 0,
    currentPage: 1,
    limit: 20
  };

  // Debounce API calls for AI evaluation updates
  const invalidateItemsTimeoutRef = useRef(null);

  // WebSocket Integration for Real-time AI Updates
  useEffect(() => {
    const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/crawl-status`;
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'AI_EVALUATION_DONE') {
          console.log(`AI evaluated ${message.count} items. Invalidating queries...`);
          
          // Clear previous timeout if exists
          if (invalidateItemsTimeoutRef.current) {
            clearTimeout(invalidateItemsTimeoutRef.current);
          }
          
          // Set a new timeout to debounce the invalidateQueries call (2 seconds)
          invalidateItemsTimeoutRef.current = setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ['items'] });
            queryClient.invalidateQueries({ queryKey: ['aiPendingCount'] });
          }, 2000);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    return () => {
      // Clear timeout on unmount
      if (invalidateItemsTimeoutRef.current) {
        clearTimeout(invalidateItemsTimeoutRef.current);
      }
      
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCheckboxChange = (itemId) => {
    const newSelected = new Set(selectedItems);
    if (newSelected.has(itemId)) {
      newSelected.delete(itemId);
    } else {
      newSelected.add(itemId);
    }
    setSelectedItems(newSelected);
  };

  const handlePageChange = (newPage) => {
    setFilters(prev => ({ ...prev, page: newPage }));
    setSelectedItems(new Set());
  };

  return (
    <div className="item-list-container">
      <ItemFilters 
        filters={filters} 
        setFilters={setFilters} 
        onOpenBulkEvaluate={() => setBulkEvaluationState(prev => ({ ...prev, isOpen: true }))}
        aiPendingCount={aiPendingCount}
      />

      <ItemActions 
        items={items}
        selectedItems={selectedItems}
        setSelectedItems={setSelectedItems}
        filters={filters}
      />

      <Pagination
        currentPage={pagination.currentPage}
        totalPages={pagination.totalPages}
        onPageChange={handlePageChange}
      />

      <ul className="item-list">
        {items.map(item => (
          <ItemCard 
            key={item._id}
            item={item}
            isSelected={selectedItems.has(item._id)}
            onCheckboxChange={handleCheckboxChange}
          />
        ))}
      </ul>

      <BulkEvaluationModal state={bulkEvaluationState} setState={setBulkEvaluationState} />
    </div>
  );
};

export default ItemList;