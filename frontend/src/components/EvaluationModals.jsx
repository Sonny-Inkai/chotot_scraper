import React from 'react';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';

export const BulkEvaluationModal = ({ state, setState }) => {
  const queryClient = useQueryClient();

  const handleBulkEvaluate = async () => {
    try {
      const evaluations = JSON.parse(state.jsonInput);
      
      if (!Array.isArray(evaluations)) {
        throw new Error('Input must be an array of evaluations');
      }

      const validEvaluations = evaluations.map(evaluation => {
        const baseEval = {
          _id: parseInt(evaluation._id),
          type: parseInt(evaluation.type),
          note: evaluation.note || ''
        };

        if (parseInt(evaluation.type) === 1) {
          if (evaluation.buy_price) baseEval.buy_price = parseInt(evaluation.buy_price);
          if (evaluation.sell_price) baseEval.sell_price = parseInt(evaluation.sell_price);
          if (evaluation.new_title) baseEval.new_title = evaluation.new_title;
        }

        return baseEval;
      });

      const response = await axios.put(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/items/bulk-evaluate`, {
        evaluations: validEvaluations
      });

      if (response.data.success) {
        queryClient.invalidateQueries({ queryKey: ['items'] });
        setState({ isOpen: false, jsonInput: '', error: null });
        alert('Bulk evaluation completed successfully!');
      }
    } catch (error) {
      console.error('Error in bulk evaluation:', error);
      setState(prev => ({ ...prev, error: error.message }));
    }
  };

  if (!state.isOpen) return null;

  return (
    <div className="bulk-evaluation-modal">
      <div className="bulk-evaluation-content">
        <h3>Bulk Insert Evaluations</h3>
        <textarea
          className="bulk-evaluation-input"
          value={state.jsonInput}
          onChange={(e) => setState(prev => ({ ...prev, jsonInput: e.target.value, error: null }))}
          placeholder={`[{"_id": 122989972, "type": 2, "note": "Giá hơi cao so với tình trạng màn hình bị ám nhẹ. Đề xuất thương lượng giá 400k."}]`}
        />
        {state.error && (
          <div className="bulk-evaluation-error">
            {state.error}
          </div>
        )}
        <div className="bulk-evaluation-buttons">
          <button onClick={handleBulkEvaluate}>Done</button>
          <button onClick={() => setState({ isOpen: false, jsonInput: '', error: null })}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};