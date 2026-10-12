import React, { useEffect, useState } from 'react';
import { Search, Filter, X, Trash2, CheckSquare, Square, AlertTriangle, RefreshCw } from 'lucide-react';
import FileCard from './FileCard';
import useFileStore from '../store/fileStore';
import toast from 'react-hot-toast';

const FileBrowser = () => {
  const {
    files,
    searchResults,
    searchQuery,
    isLoading,
    error,
    totalFiles,
    selectedFileIds,
    listFiles,
    searchFiles,
    downloadFile,
    deleteFile,
    bulkDeleteSelected,
    toggleSelectFile,
    selectAllFiles,
    deselectAllFiles,
    clearSelection,
    clearSearch,
  } = useFileStore();

  const [filters, setFilters] = useState({
    file_type: '',
    department: '',
  });
  const [showFilters, setShowFilters] = useState(false);

  // Bulk Delete Modal State
  const [showBulkDeleteModal, setShowBulkDeleteModal] = useState(false);
  const [permanentDelete, setPermanentDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    listFiles();
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const query = formData.get('query');
    if (query?.trim()) {
      await searchFiles(query, filters);
    }
  };

  const handleClearSearch = () => {
    clearSearch();
    listFiles();
  };

  const handleDelete = async (fileId) => {
    if (window.confirm('Are you sure you want to delete this file?')) {
      try {
        await deleteFile(fileId);
        toast.success('File deleted successfully');
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to delete file');
      }
    }
  };

  const handleDownload = async (fileId, filename) => {
    try {
      await downloadFile(fileId, filename);
    } catch (err) {
      toast.error('Failed to download file');
    }
  };

  const displayFiles = searchQuery ? searchResults : files;
  const isAllSelected = displayFiles.length > 0 && displayFiles.every(f => selectedFileIds.includes(f.id));

  const handleToggleSelectAll = () => {
    if (isAllSelected) {
      deselectAllFiles();
    } else {
      selectAllFiles();
    }
  };

  const handleConfirmBulkDelete = async () => {
    setIsDeleting(true);
    try {
      const result = await bulkDeleteSelected(permanentDelete);
      if (result.deleted_count > 0 && (!result.failed_ids || result.failed_ids.length === 0)) {
        toast.success(`Successfully deleted ${result.deleted_count} file(s).`);
      } else if (result.deleted_count > 0 && result.failed_ids && result.failed_ids.length > 0) {
        toast.error(
          `Partial Success: Deleted ${result.deleted_count} file(s), but ${result.failed_ids.length} file(s) failed (unauthorized or protected records).`,
          { duration: 6000 }
        );
      } else if (result.deleted_count === 0 && result.failed_ids && result.failed_ids.length > 0) {
        toast.error(
          `Deletion Failed: None of the ${result.failed_ids.length} selected files could be deleted (unauthorized or protected dependencies).`,
          { duration: 6000 }
        );
      } else {
        toast.info('No files were deleted.');
      }
      setShowBulkDeleteModal(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk deletion failed');
    } finally {
      setIsDeleting(false);
    }
  };


  return (
    <div className="max-w-6xl mx-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Institutional Files</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Browse, search, upload, and organize campus documents and academic files.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => listFiles(filters)}
            className="px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg flex items-center gap-1.5 transition-colors"
            title="Refresh Files"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center space-x-1.5 px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 transition-colors"
          >
            <Filter className="w-4 h-4" />
            <span>Filters</span>
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex space-x-2">
        <div className="flex-1 relative">
          <input
            name="query"
            type="text"
            placeholder="Search documents by keywords, tags, or content..."
            defaultValue={searchQuery}
            className="w-full px-4 py-2 pl-10 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-indigo-500 text-sm"
          />
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium transition-colors"
        >
          Search
        </button>
        {searchQuery && (
          <button
            type="button"
            onClick={handleClearSearch}
            className="px-3 py-2 text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </form>

      {/* Filters Drawer */}
      {showFilters && (
        <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">File Type</label>
            <select
              value={filters.file_type}
              onChange={(e) => setFilters(prev => ({ ...prev, file_type: e.target.value }))}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
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
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Department</label>
            <select
              value={filters.department}
              onChange={(e) => setFilters(prev => ({ ...prev, department: e.target.value }))}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
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
              listFiles();
            }}
            className="px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-gray-800 rounded-lg"
          >
            Reset Filters
          </button>
        </div>
      )}

      {/* Bulk Operations Toolbar */}
      {displayFiles.length > 0 && (
        <div className="bg-white dark:bg-gray-900 p-3 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <button
              onClick={handleToggleSelectAll}
              className="flex items-center space-x-2 text-sm text-gray-700 dark:text-gray-300 font-medium hover:text-gray-900 dark:hover:text-white transition-colors"
            >
              {isAllSelected ? (
                <CheckSquare className="w-5 h-5 text-indigo-600" />
              ) : (
                <Square className="w-5 h-5 text-gray-400" />
              )}
              <span>Select All ({displayFiles.length})</span>
            </button>

            {selectedFileIds.length > 0 && (
              <span className="text-xs bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-semibold px-2.5 py-1 rounded-full border border-indigo-200 dark:border-indigo-800">
                {selectedFileIds.length} {selectedFileIds.length === 1 ? 'file' : 'files'} selected
              </span>
            )}
          </div>

          {selectedFileIds.length > 0 && (
            <div className="flex items-center space-x-2">
              <button
                onClick={clearSelection}
                className="px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                Clear Selection
              </button>
              <button
                onClick={() => setShowBulkDeleteModal(true)}
                className="px-3.5 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg flex items-center gap-1.5 shadow-sm transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                <span>Delete Selected ({selectedFileIds.length})</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Results Count */}
      {searchQuery && (
        <p className="text-sm text-gray-500">
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
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          {error}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && displayFiles.length === 0 && (
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="text-gray-400 dark:text-gray-500 text-lg font-medium">No files found</div>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            {searchQuery ? 'Try a different search term or clear filters' : 'Upload your first file to get started'}
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
            isSelected={selectedFileIds.includes(file.id)}
            onToggleSelect={toggleSelectFile}
          />
        ))}
      </div>

      {/* Bulk Delete Confirmation Modal */}
      {showBulkDeleteModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4 border border-gray-200 dark:border-gray-800">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-950/40 text-red-600 dark:text-red-400 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Confirm Bulk File Deletion</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {selectedFileIds.length} {selectedFileIds.length === 1 ? 'file' : 'files'} selected for deletion
                </p>
              </div>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-300">
              Are you sure you want to delete these {selectedFileIds.length} selected files? 
              Only files you have permission to delete (your own uploads or department files for HODs) will be processed.
            </p>

            <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
              <label className="flex items-center space-x-2 text-xs text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={permanentDelete}
                  onChange={(e) => setPermanentDelete(e.target.checked)}
                  className="rounded text-red-600 focus:ring-red-500 w-4 h-4 cursor-pointer"
                />
                <span>Permanently delete objects from storage and vector index</span>
              </label>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowBulkDeleteModal(false)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmBulkDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
              >
                {isDeleting && <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>}
                <span>{isDeleting ? 'Deleting...' : `Confirm Delete (${selectedFileIds.length})`}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileBrowser;