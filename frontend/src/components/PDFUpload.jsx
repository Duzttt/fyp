import { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { uploadPDF } from '../services/api';

export default function PDFUpload({ onUploadSuccess }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      await handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = async (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      await handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file.type.includes('pdf')) {
      setError('Please upload a PDF file');
      setUploadStatus(null);
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      setUploadStatus(null);
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadStatus(null);

    try {
      const result = await uploadPDF(file);
      setUploadStatus(result);
      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="w-full">
      <div
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 cursor-pointer
          ${isDragging 
            ? 'border-primary bg-primary/5' 
            : 'border-slate-300 hover:border-primary hover:bg-slate-50'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div className="flex flex-col items-center gap-3">
          <div className={`
            w-12 h-12 rounded-lg flex items-center justify-center
            ${isDragging ? 'bg-primary text-white' : 'bg-primary/10 text-primary'}
          `}>
            {isUploading ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <Upload className="w-6 h-6" />
            )}
          </div>

          <div>
            <p className="font-medium text-text">
              {isUploading ? 'Uploading...' : 'Drop PDF here or click to browse'}
            </p>
            <p className="text-sm text-muted mt-1">
              Maximum file size: 10MB
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted">
            <FileText className="w-4 h-4" />
            <span>PDF only</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-600">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {uploadStatus && (
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-sm text-green-700">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <div>
            <span className="font-medium">{uploadStatus.message}</span>
            {uploadStatus.chunks_created && (
              <span className="ml-2 text-green-600">({uploadStatus.chunks_created} chunks)</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
