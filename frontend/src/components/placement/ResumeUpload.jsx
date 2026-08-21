import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { useResumeStore } from '../../store/resumeStore';
import toast from 'react-hot-toast';

const ResumeUpload = ({ onUploadSuccess, studentId = null }) => {
  const [file, setFile] = useState(null);
  const { isUploading, uploadProgress, uploadResume } = useResumeStore();

  const onDrop = useCallback((acceptedFiles) => {
    const selectedFile = acceptedFiles[0];
    if (selectedFile) {
      const validTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/jpeg',
        'image/png',
      ];
      
      if (!validTypes.includes(selectedFile.type)) {
        toast.error('Please upload PDF, DOCX, JPG, or PNG files only');
        return;
      }
      
      setFile(selectedFile);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    maxFiles: 1,
  });

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a file first');
      return;
    }

    try {
      const result = await uploadResume(file, studentId);
      
      if (result.success) {
        toast.success('Resume uploaded successfully!');
        setFile(null);
        if (onUploadSuccess) {
          onUploadSuccess(result);
        }
      } else {
        toast.error(result.message || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error(error.response?.data?.detail || 'Failed to upload resume');
    }
  };

  const removeFile = () => {
    setFile(null);
  };

  const getFileIcon = () => {
    if (!file) return null;
    const type = file.type;
    if (type === 'application/pdf') return '📄';
    if (type.includes('word')) return '📝';
    if (type.includes('image')) return '🖼️';
    return '📎';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">Upload Resume</h3>
      
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400'}
          ${file ? 'bg-green-50 border-green-400' : ''}
        `}
      >
        <input {...getInputProps()} />
        
        {file ? (
          <div className="flex items-center justify-center gap-3">
            <span className="text-3xl">{getFileIcon()}</span>
            <div className="text-left">
              <p className="font-medium text-gray-800">{file.name}</p>
              <p className="text-sm text-gray-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFile();
              }}
              className="ml-4 p-1 hover:bg-gray-100 rounded-full"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        ) : (
          <>
            <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-600">
              {isDragActive ? 'Drop your resume here' : 'Drag & drop your resume here'}
            </p>
            <p className="text-sm text-gray-400 mt-1">
              or click to browse (PDF, DOCX, JPG, PNG)
            </p>
          </>
        )}
      </div>

      {/* Upload Progress */}
      {isUploading && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
            <span>Uploading...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Upload Button */}
      <button
        onClick={handleUpload}
        disabled={!file || isUploading}
        className={`
          w-full mt-4 py-2 px-4 rounded-lg font-medium transition-colors
          ${!file || isUploading
            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
            : 'bg-indigo-600 text-white hover:bg-indigo-700'
          }
        `}
      >
        {isUploading ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            Uploading...
          </span>
        ) : (
          'Upload Resume'
        )}
      </button>

      <p className="text-xs text-gray-400 mt-2 text-center">
        Supported formats: PDF, DOCX, JPG, PNG • Max size: 10MB
      </p>
    </div>
  );
};

export default ResumeUpload;