import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, FileText } from 'lucide-react';
import { previewFile } from '../services/fileService';

const FilePreview = ({ fileId, filename, mimeType }) => {
  const [showPreview, setShowPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');

  useEffect(() => {
    if (showPreview && fileId) {
      setPreviewUrl(previewFile(fileId));
    }
  }, [showPreview, fileId]);

  const isPreviewable = () => {
    if (!mimeType) return false;
    const previewableTypes = [
      'image/jpeg', 'image/png', 'image/gif', 'image/svg+xml',
      'application/pdf', 'text/plain',
    ];
    return previewableTypes.some(type => mimeType.includes(type));
  };

  if (!isPreviewable()) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 text-center">
        <FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-sm text-gray-500">Preview not available for this file type</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-lg overflow-hidden">
      <button
        onClick={() => setShowPreview(!showPreview)}
        className="w-full px-4 py-2 text-left text-sm text-gray-600 hover:bg-gray-100 flex items-center space-x-2"
      >
        {showPreview ? (
          <>
            <EyeOff className="w-4 h-4" />
            <span>Hide Preview</span>
          </>
        ) : (
          <>
            <Eye className="w-4 h-4" />
            <span>Show Preview</span>
          </>
        )}
      </button>

      {showPreview && (
        <div className="p-4">
          {mimeType?.startsWith('image/') ? (
            <img
              src={previewUrl}
              alt="Preview"
              className="max-h-96 mx-auto rounded-lg shadow-sm"
            />
          ) : mimeType === 'application/pdf' ? (
            <iframe
              src={previewUrl}
              className="w-full h-96 rounded-lg border border-gray-200"
              title="PDF Preview"
            />
          ) : mimeType === 'text/plain' ? (
            <iframe
              src={previewUrl}
              className="w-full h-64 rounded-lg border border-gray-200"
              title="Text Preview"
            />
          ) : (
            <div className="text-center py-8">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500">Preview not supported for this file type</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FilePreview;