import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import FileBrowser from '../components/FileBrowser';
import FileUpload from '../components/FileUpload';
import FileDetail from './FileDetail';

const FileManager = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route index element={<FileBrowser />} />
        <Route path="upload" element={<FileUpload />} />
        <Route path=":fileId" element={<FileDetail />} />
        <Route path="*" element={<Navigate to="/files" replace />} />
      </Routes>
    </div>
  );
};

export default FileManager;