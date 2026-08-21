import React, { useEffect, useState } from 'react';
import { Search, Filter, X } from 'lucide-react';
import FileCard from './FileCard';
import useFileStore from '../store/fileStore';

const FileBrowser = () => {
  const {
    files,
    searchResults,
    searchQuery,
    isLoading,
    error,
    totalFiles,
    listFiles,
    searchFiles,
    downloadFile,
    deleteFile,
    clearSearch,
  } = useFileStore();

  const [viewMode, setViewMode] = useState('grid'); // grid, list
  const [filters, setFilters] = useState({
    file_type: '',
    department: '',
  });
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    listFiles();
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const query = formData.get('query');
    if (query.trim()) {
      await searchFiles(query, filters);
    }
  };

  const handleClearSearch = () => {
    clearSearch();
    listFiles();
  };

  const handleDelete = async (fileId) => {
    if (window.confirm('Are you sure you want to delete this file?')) {
      await deleteFile(fileId);
    }
  };

  const handleDownload = async (fileId, filename) => {
    await downloadFile(fileId, filename);
  };

  const displayFiles = searchQuery ? searchResults : files;

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Files</h1>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center space-x-2 px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg"
        >
          <Filter className="w-4 h-4" />
          <span>Filters</span>
        </button>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex space-x-2 mb-4">
        <div className="flex-1 relative">
          <input
            name="query"
            type="text"
            placeholder="Search files..."
            defaultValue={searchQuery}
            className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
          />
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          Search
        </button>
        {searchQuery && (
          <button
            type="button"
            onClick={handleClearSearch}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </form>

      {/* Filters */}
      {showFilters && (
        <div className="bg-gray-50 rounded-lg p-4 mb-4 flex flex-wrap gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              File Type
            </label>
            <select
              value={filters.file_type}
              onChange={(e) => setFilters(prev => ({ ...prev, file_type: e.target.value }))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="">All Types</option>
              <option value="exam_duty">Exam Duty</option>
              <option value="assignment">Assignment</option>
              <option value="circular">Circular</option>
              <option value="resume">Resume</option>
              <option value="timetable">Timetable</option>
              <option value="certificate">Certificate</option>
              <option value="placement_doc">Placement Document</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Department
            </label>
            <select
              value={filters.department}
              onChange={(e) => setFilters(prev => ({ ...prev, department: e.target.value }))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="">All Departments</option>
              <option value="CS">CS</option>
              <option value="IT">IT</option>
              <option value="EC">EC</option>
              <option value="EE">EE</option>
              <option value="ME">ME</option>
              <option value="CE">CE</option>
            </select>
          </div>
          <button
            onClick={() => {
              setFilters({ file_type: '', department: '' });
            }}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-200 rounded-lg self-end"
          >
            Clear Filters
          </button>
        </div>
      )}

      {/* Results Count */}
      {searchQuery && (
        <p className="text-sm text-gray-500 mb-4">
          Found {totalFiles} results for "{searchQuery}"
        </p>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">
          {error}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && displayFiles.length === 0 && (
        <div className="text-center py-12">
          <div className="text-gray-400 text-lg">No files found</div>
          <p className="text-gray-500 text-sm mt-2">
            {searchQuery ? 'Try a different search term' : 'Upload your first file'}
          </p>
        </div>
      )}

      {/* File Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {displayFiles.map((file) => (
          <FileCard
            key={file.id}
            file={file}
            onDelete={handleDelete}
            onDownload={handleDownload}
          />
        ))}
      </div>
    </div>
  );
};

export default FileBrowser;