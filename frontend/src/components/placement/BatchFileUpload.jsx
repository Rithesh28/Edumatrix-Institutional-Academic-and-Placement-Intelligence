import React, { useState } from 'react';
import { Upload, File, X, CheckCircle, AlertCircle, Loader, Calendar } from 'lucide-react';
import toast from 'react-hot-toast';
import { API_URL } from '../../services/api';

const BatchFileUpload = ({ jobPostingId, onUploadComplete }) => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [extractedData, setExtractedData] = useState(null);

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    const validFiles = selectedFiles.filter(file => {
      const validTypes = ['application/pdf', 'image/jpeg', 'image/png', 'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      return validTypes.includes(file.type) || file.name.endsWith('.pdf') || 
        file.name.endsWith('.docx') || file.name.endsWith('.doc') ||
        file.name.endsWith('.jpg') || file.name.endsWith('.jpeg') || file.name.endsWith('.png');
    });

    if (validFiles.length !== selectedFiles.length) {
      toast.error('Some files were skipped. Only PDF, DOCX, DOC, JPG, PNG files are supported.');
    }

    setFiles(prev => [...prev, ...validFiles]);
    e.target.value = '';
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const token = localStorage.getItem('auth-storage') 
        ? JSON.parse(localStorage.getItem('auth-storage')).state?.token 
        : '';

      const formData = new FormData();

      // Add all files
      files.forEach((file) => {
        formData.append('files', file);
      });

      // Add metadata
      if (jobPostingId) {
        formData.append('job_posting_id', jobPostingId);
      }
      formData.append('auto_extract', 'true');
      formData.append('auto_schedule_reminders', 'true');

      // Simulate progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 300);

      const response = await fetch(`${API_URL}/placement/batch-upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      if (response.ok) {
        const result = await response.json();
        setExtractedData(result);
        
        toast.success(`Uploaded ${result.processed || files.length} files successfully!`);
        
        // Show extracted dates info
        if (result.extracted_dates && result.extracted_dates.length > 0) {
          toast.info(`📅 Extracted ${result.extracted_dates.length} dates from files`);
        }
        
        if (result.reminders_scheduled) {
          toast.success(`⏰ ${result.reminders_scheduled} reminders scheduled!`);
        }
        
        setFiles([]);
        if (onUploadComplete) onUploadComplete(result);
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Upload failed');
      }
    } catch (error) {
      toast.error('Failed to upload files');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-2">📤 Batch Upload Files</h3>
      <p className="text-sm text-gray-500 mb-4">
        Upload multiple PDFs, DOCX, or Images. The system will auto-extract dates and send reminders to students.
      </p>

      {/* Drop Zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          files.length > 0 ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400'
        }`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFileSelect({ target: { files: e.dataTransfer.files } });
        }}
      >
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.doc,.jpg,.jpeg,.png"
          onChange={handleFileSelect}
          className="hidden"
          id="batch-file-upload"
        />
        <label htmlFor="batch-file-upload" className="cursor-pointer">
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600">Drag & drop files here, or click to select</p>
          <p className="text-sm text-gray-400 mt-1">Supports: PDF, DOCX, DOC, JPG, PNG (Max 10 files)</p>
        </label>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-4 space-y-2 max-h-60 overflow-y-auto">
          {files.map((file, index) => (
            <div key={index} className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
              <div className="flex items-center space-x-3">
                <File className="w-5 h-5 text-gray-500" />
                <div>
                  <p className="text-sm font-medium text-gray-700 truncate max-w-xs">{file.name}</p>
                  <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
              <button
                onClick={() => removeFile(index)}
                className="p-1 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Extracted Data Preview */}
      {extractedData && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="font-medium text-green-700">Processing Complete</span>
          </div>
          <div className="mt-2 text-sm text-green-600">
            <p>✅ Files processed: {extractedData.processed || files.length}</p>
            {extractedData.extracted_dates && (
              <p>📅 Dates extracted: {extractedData.extracted_dates.length}</p>
            )}
            {extractedData.reminders_scheduled && (
              <p>⏰ Reminders scheduled: {extractedData.reminders_scheduled}</p>
            )}
          </div>
        </div>
      )}

      {/* Upload Button */}
      {files.length > 0 && !extractedData && (
        <div className="mt-4">
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          >
            {uploading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                <span>Uploading... {uploadProgress}%</span>
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                <span>Upload {files.length} file{files.length > 1 ? 's' : ''}</span>
              </>
            )}
          </button>
          <p className="text-xs text-gray-400 mt-2 text-center">
            Files will be processed and deadlines extracted automatically
          </p>
        </div>
      )}

      {/* Clear/Reset Button */}
      {extractedData && (
        <div className="mt-4">
          <button
            onClick={() => {
              setExtractedData(null);
              setFiles([]);
              setUploadProgress(0);
            }}
            className="w-full py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
          >
            Upload More Files
          </button>
        </div>
      )}
    </div>
  );
};

export default BatchFileUpload;