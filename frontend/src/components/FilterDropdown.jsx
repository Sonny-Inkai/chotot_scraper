import React, { useState, useEffect, useRef, useMemo } from 'react';
import '../styles/FilterDropdown.css'; // We'll create this file next

const FilterDropdown = ({
  options, // Object: { value: label, ... }
  selectedOptions, // Array for multi-select, String for single-select
  onChange, // Function to call when selection changes
  label,
  placeholder = "Select...",
  isMultiSelect = false,
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm(''); // Clear search on close
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const filteredOptions = useMemo(() => {
    if (!searchTerm) {
      return Object.entries(options); // [ [value, label], ... ]
      }
      const lowerSearchTerm = searchTerm.toLowerCase();
      // Filter only based on the label (the second element in the entry array)
      return Object.entries(options).filter(([, label]) =>
      label.toLowerCase().includes(lowerSearchTerm)
    );
  }, [options, searchTerm]);

  const handleToggleDropdown = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
       if (isOpen) setSearchTerm(''); // Clear search on close
    }
  };

  const handleCheckboxChange = (event) => {
    const { value, checked } = event.target;

    if (isMultiSelect) {
      let newSelection;
      if (value === 'all') {
        // Handle "Select All" for filtered options
        const allFilteredValues = filteredOptions.map(([val]) => val);
        if (checked) {
          // Add all filtered values to the current selection, avoiding duplicates
          newSelection = Array.from(new Set([...selectedOptions, ...allFilteredValues]));
        } else {
          // Remove all filtered values from the current selection
          const filteredValuesSet = new Set(allFilteredValues);
          newSelection = selectedOptions.filter(opt => !filteredValuesSet.has(opt));
        }
      } else {
        // Handle individual checkbox
        newSelection = checked
          ? [...selectedOptions, value]
          : selectedOptions.filter((option) => option !== value);
      }
      onChange(newSelection);
    } else {
      // Single select logic
      onChange(value);
      setIsOpen(false); // Close dropdown after single selection
      setSearchTerm('');
    }
  };

  const getDisplayValue = () => {
    if (isMultiSelect) {
      if (!selectedOptions || selectedOptions.length === 0) {
        return placeholder;
      }
      if (selectedOptions.length === Object.keys(options).length) {
          return `All ${label} Selected`;
      }
      if (selectedOptions.length > 2) {
        return `${selectedOptions.length} ${label} Selected`;
      }
      return selectedOptions.map(val => options[val] || val).join(', ');
    } else {
      // Single select display
      return options[selectedOptions] || placeholder;
    }
  };

  // Determine if "Select All" should be checked based on filtered options
  const allFilteredSelected = useMemo(() => {
      if (!isMultiSelect || filteredOptions.length === 0) return false;
      const filteredValuesSet = new Set(filteredOptions.map(([val]) => val));
      return selectedOptions.filter(opt => filteredValuesSet.has(opt)).length === filteredOptions.length;
  }, [filteredOptions, selectedOptions, isMultiSelect]);


  return (
    <div className={`filter-dropdown ${disabled ? 'disabled' : ''}`} ref={dropdownRef}>
      <label className="dropdown-label">{label}</label>
      <div className="dropdown-header" onClick={handleToggleDropdown}>
        <span>{getDisplayValue()}</span>
        <span className={`dropdown-arrow ${isOpen ? 'open' : ''}`}>▼</span>
      </div>
      {isOpen && (
        <div className="dropdown-list-container">
          <input
            type="text"
            className="dropdown-search"
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            autoFocus
          />
          <ul className="dropdown-list">
            {isMultiSelect && filteredOptions.length > 0 && (
              <li className="dropdown-item select-all-item">
                <input
                  type="checkbox"
                  id={`${label}-select-all-filtered`}
                  value="all"
                  checked={allFilteredSelected}
                  onChange={handleCheckboxChange}
                />
                <label htmlFor={`${label}-select-all-filtered`}>Select All (Filtered)</label>
              </li>
            )}
            {filteredOptions.length > 0 ? (
              filteredOptions.map(([value, itemLabel]) => (
                <li key={value} className="dropdown-item">
                  {isMultiSelect ? (
                    <>
                      <input
                        type="checkbox"
                        id={`${label}-${value}`}
                        value={value}
                        checked={selectedOptions.includes(value)}
                        onChange={handleCheckboxChange}
                      />
                      <label htmlFor={`${label}-${value}`}>{itemLabel}</label>
                    </>
                  ) : (
                    <div
                      className={`option ${selectedOptions === value ? 'selected' : ''}`}
                      onClick={() => handleCheckboxChange({ target: { value: value, checked: true } })} // Simulate checkbox change for single select
                    >
                      {itemLabel}
                    </div>
                  )}
                </li>
              ))
            ) : (
              <li className="dropdown-item no-results">No results found</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
};

export default FilterDropdown;