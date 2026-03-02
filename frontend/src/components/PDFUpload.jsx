import { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
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

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200
          ${isDragging 
            ? 'border-primary bg-primary/5' 
            : 'border-slate-300 hover:border-primary/50 hover:bg-slate-50'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={triggerFileInput}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div className="flex flex-col items-center gap-4">
          <div className={`
            w-16 h-16 rounded-full flex items-center justify-center transition-colors duration-200
            ${isDragging ? 'bg-primary text-white' : 'bg-primary/10 text-primary'}
          `}>
            {isUploading ? (
              <Loader2 className="w-8 h-8 animate-spin" />
            ) : (
              <Upload className="w-8 h-8" />
            )}
          </div>

          <div>
            <p className="text-lg font-semibold text-text">
              {isUploading ? 'Uploading...' : 'Drop your PDF here'}
            </p>
            <p className="text-sm text-slate-500 mt-1">
              or click to browse (max 10MB)
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <FileText className="w-4 h-4" />
            <span>PDF files only</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-700">Upload Failed</p>
            <p className="text-sm text-red-600 mt-1">{error}</p>
          </div>
        </div>
      )}

      {uploadStatus && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-green-700">Upload Successful</p>
            <p className="text-sm text-green-600 mt-1">
              {uploadStatus.message}
            </p>
            {uploadStatus.chunks_created && (
              <p className="text-xs text-green-500 mt-2">
                {uploadStatus.chunks_created} chunks created
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
