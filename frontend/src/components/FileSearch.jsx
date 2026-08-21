import React, { useState, useEffect, useCallback } from 'react';
import { Search, X, Filter, ChevronDown, ChevronUp } from 'lucide-react';
import { debounce } from 'lodash';
import useFileStore from '../store/fileStore';
import FileCard from './FileCard';

const FILE_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'exam_duty', label: 'Exam Duty' },
  { value: 'assignment', label: 'Assignment' },
  { value: 'circular', label: 'Circular' },
  { value: 'resume', label: 'Resume' },
  { value: 'timetable', label: 'Timetable' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'placement_doc', label: 'Placement Document' },
  { value: 'other', label: 'Other' },
];

const DEPARTMENTS = [
  { value: '', label: 'All Departments' },
  { value: 'CS', label: 'Computer Science' },
  { value: 'IT', label: 'Information Technology' },
  { value: 'EC', label: 'Electronics & Communication' },
  { value: 'EE', label: 'Electrical Engineering' },
  { value: 'ME', label: 'Mechanical Engineering' },
  { value: 'CE', label: 'Civil Engineering' },
  { value: 'MBA', label: 'MBA' },
  { value: 'MCA', label: 'MCA' },
];

const FileSearch = () => {
  const {
    searchResults,
    searchQuery,
    isLoading,
    error,
    totalFiles,
    searchFiles,
    clearSearch,
    downloadFile,
    deleteFile,
    getSuggestions,
  } = useFileStore();

  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({
    file_type: '',
    department: '',
  });
  const [showFilters, setShowFilters] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Debounced search
  const debouncedSearch = useCallback(
    debounce(async (searchQuery, searchFilters) => {
      if (searchQuery.trim().length >= 2) {
        await searchFiles(searchQuery, searchFilters);
      } else if (searchQuery.trim().length === 0) {
        clearSearch();
      }
    }, 500),
    []
  );

  // Debounced suggestions
  const debouncedSuggestions = useCallback(
    debounce(async (input) => {
      if (input.trim().length >= 2) {
        const results = await getSuggestions(input);
        setSuggestions(results);
        setShowSuggestions(true);
      } else {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    }, 300),
    []
  );

  useEffect(() => {
    if (query.trim().length >= 2) {
      debouncedSearch(query, filters);
      debouncedSuggestions(query);
    } else {
      clearSearch();
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [query, filters]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim().length >= 2) {
      searchFiles(query, filters);
    }
  };

  const handleClear = () => {
    setQuery('');
    clearSearch();
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleSuggestionClick = (suggestion) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    searchFiles(suggestion, filters);
  };

  const handleDelete = async (fileId) => {
    if (window.confirm('Are you sure you want to delete this file?')) {
      await deleteFile(fileId);
      // Refresh search results
      if (query.trim().length >= 2) {
        await searchFiles(query, filters);
      }
    }
  };

  const handleDownload = async (fileId, filename) => {
    await downloadFile(fileId, filename);
  };

  const hasResults = searchResults && searchResults.length > 0;

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Search Files</h1>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="relative">
        <div className="flex items-center bg-white rounded-lg shadow-sm border border-gray-300 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent">
          <Search className="w-5 h-5 text-gray-400 ml-3 flex-shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.trim().length >= 2 && setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            placeholder="Search for files by content, title, or description..."
            className="w-full px-3 py-3 outline-none bg-transparent text-gray-900 placeholder-gray-400"
          />
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="p-2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`p-2 text-gray-400 hover:text-gray-600 border-l border-gray-200 ${
              showFilters ? 'bg-gray-50' : ''
            }`}
          >
            <Filter className="w-4 h-4" />
          </button>
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 text-white rounded-r-lg hover:bg-indigo-700 transition-colors"
          >
            Search
          </button>
        </div>

        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-10 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-y-auto">
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => handleSuggestionClick(suggestion)}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
              >
                <Search className="w-3 h-3 text-gray-400" />
                <span>{suggestion}</span>
              </button>
            ))}
          </div>
        )}
      </form>

      {/* Filters */}
      {showFilters && (
        <div className="mt-4 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                File Type
              </label>
              <select
                value={filters.file_type}
                onChange={(e) => handleFilterChange('file_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
              >
                {FILE_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Department
              </label>
              <select
                value={filters.department}
                onChange={(e) => handleFilterChange('department', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
              >
                {DEPARTMENTS.map(dept => (
                  <option key={dept.value} value={dept.value}>
                    {dept.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => {
                setFilters({ file_type: '', department: '' });
              }}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear Filters
            </button>
          </div>
        </div>
      )}

      {/* Results */}
      {query && (
        <div className="mt-6">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg">
              {error}
            </div>
          ) : !hasResults && query.trim().length >= 2 ? (
            <div className="text-center py-12">
              <div className="text-gray-400 text-lg">No results found</div>
              <p className="text-gray-500 text-sm mt-2">
                Try adjusting your search terms or filters
              </p>
            </div>
          ) : hasResults ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-gray-500">
                  Found {totalFiles} result{totalFiles !== 1 ? 's' : ''} for "{query}"
                </p>
                <button
                  onClick={handleClear}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Clear Search
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {searchResults.map((file) => (
                  <FileCard
                    key={file.file_id || file.id}
                    file={{ ...file, id: file.file_id || file.id }}
                    onDelete={handleDelete}
                    onDownload={handleDownload}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500">
                Enter a search term to find files
              </p>
            </div>
          )}
        </div>
      )}

      {/* Empty state when no search */}
      {!query && (
        <div className="text-center py-12">
          <Search className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 text-lg">
            Search for files by content, title, or description
          </p>
          <p className="text-gray-400 text-sm mt-1">
            Try searching for "machine learning", "exam duty", or "assignment"
          </p>
        </div>
      )}
    </div>
  );
};

export default FileSearch;