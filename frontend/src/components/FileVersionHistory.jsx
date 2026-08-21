import React, { useState, useEffect } from 'react';
import { GitBranch, Clock, User, Download, RotateCcw } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { getFileVersions, restoreVersion, downloadFile } from '../services/fileService';
import useFileStore from '../store/fileStore';

const FileVersionHistory = ({ fileId }) => {
  const [versions, setVersions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const { downloadFile: downloadFileAction } = useFileStore();

  useEffect(() => {
    if (expanded && fileId) {
      loadVersions();
    }
  }, [expanded, fileId]);

  const loadVersions = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getFileVersions(fileId);
      setVersions(data || []);
    } catch (err) {
      setError('Failed to load version history');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestore = async (versionNumber) => {
    if (!window.confirm(`Restore version ${versionNumber}?`)) return;
    try {
      await restoreVersion(fileId, versionNumber);
      await loadVersions();
      alert('Version restored successfully!');
    } catch (err) {
      alert('Failed to restore version');
      console.error(err);
    }
  };

  const handleDownloadVersion = async (version) => {
    await downloadFileAction(version.file_id, `v${version.version_number}_${version.filename || 'file'}`);
  };

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-800"
      >
        <GitBranch className="w-4 h-4" />
        <span>Version History</span>
      </button>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <GitBranch className="w-4 h-4 text-gray-500" />
          <h3 className="text-sm font-medium text-gray-900">Version History</h3>
        </div>
        <button
          onClick={() => setExpanded(false)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Close
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-2 border-indigo-600 border-t-transparent"></div>
        </div>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : versions.length === 0 ? (
        <p className="text-sm text-gray-500">No version history available</p>
      ) : (
        <div className="space-y-3">
          {versions.map((version, index) => (
            <div
              key={version.id}
              className={`flex items-center justify-between p-3 rounded-lg ${
                index === 0 ? 'bg-indigo-50 border border-indigo-200' : 'bg-gray-50'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  index === 0 ? 'bg-indigo-500 text-white' : 'bg-gray-300 text-gray-600'
                }`}>
                  <span className="text-xs font-medium">v{version.version_number}</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {index === 0 ? 'Current Version' : `Version ${version.version_number}`}
                  </p>
                  <div className="flex items-center space-x-2 text-xs text-gray-500">
                    <Clock className="w-3 h-3" />
                    <span>{formatDistanceToNow(new Date(version.created_at), { addSuffix: true })}</span>
                    {version.uploaded_by && (
                      <>
                        <span>•</span>
                        <User className="w-3 h-3" />
                        <span>User {version.uploaded_by}</span>
                      </>
                    )}
                  </div>
                  {version.change_description && (
                    <p className="text-xs text-gray-500 mt-1">{version.change_description}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-1">
                <button
                  onClick={() => handleDownloadVersion(version)}
                  className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200"
                  title="Download this version"
                >
                  <Download className="w-4 h-4" />
                </button>
                {index > 0 && (
                  <button
                    onClick={() => handleRestore(version.version_number)}
                    className="p-1.5 text-gray-400 hover:text-indigo-600 rounded-lg hover:bg-indigo-50"
                    title="Restore this version"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FileVersionHistory;