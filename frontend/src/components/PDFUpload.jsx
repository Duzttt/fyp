import { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, Sparkles } from 'lucide-react';
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

  const handleDragLeave = (e) => {
    e.preventDefault();
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
    <div className="w-full">
      <div
        className={`
          relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-300 cursor-pointer
          ${isDragging 
            ? 'border-primary bg-primary/5 scale-[1.02]' 
            : 'border-secondary/30 hover:border-primary/50 hover:bg-purple-50/50'
          }
          ${isUploading ? 'opacity-60 pointer-events-none' : ''}
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
            w-16 h-16 rounded-2xl flex items-center justify-center transition-all duration-300
            ${isDragging ? 'bg-primary text-white scale-110' : 'bg-gradient-to-br from-primary/10 to-secondary/10 text-primary'}
          `}>
            {isUploading ? (
              <Loader2 className="w-8 h-8 animate-spin" />
            ) : (
              <Upload className="w-8 h-8" />
            )}
          </div>

          <div>
            <p className="font-heading font-semibold text-lg text-text">
              {isUploading ? 'Uploading & Processing...' : 'Drop your lecture PDF'}
            </p>
            <p className="text-sm text-secondary mt-1">
              or click to browse • Max 10MB
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-secondary/70">
            <FileText className="w-4 h-4" />
            <span>PDF files only</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-100 rounded-xl flex items-start gap-3 animate-in fade-in slide-in-from-top-2">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-700">Upload Failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {uploadStatus && (
        <div className="mt-4 p-4 bg-green-50 border border-green-100 rounded-xl flex items-start gap-3 animate-in fade-in slide-in-from-top-2">
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <p className="font-medium text-green-800">Successfully Processed!</p>
            <p className="text-sm text-green-700 mt-0.5">
              {uploadStatus.message}
            </p>
            {uploadStatus.chunks_created && (
              <div className="flex items-center gap-1 mt-2">
                <Sparkles className="w-3 h-3 text-green-600" />
                <p className="text-xs text-green-600 font-medium">
                  {uploadStatus.chunks_created} text chunks created
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
