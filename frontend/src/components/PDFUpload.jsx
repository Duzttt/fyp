import { Plus, Upload, X, Loader2, CheckCircle2 } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadFile } from '../services/api';

export default function PDFUpload({ onUploadAccepted, onUploadSuccess }) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // 'idle' | 'uploading' | 'success' | 'error'
  const [isOpen, setIsOpen] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setIsUploading(true);
      setUploadStatus('uploading');
      
      if (onUploadAccepted) {
        onUploadAccepted({ filename: file.name });
      }

      try {
        const result = await uploadFile(file);
        setUploadStatus('success');
        if (onUploadSuccess) {
          onUploadSuccess(result);
        }
        // Auto close after success
        setTimeout(() => {
          setIsOpen(false);
          setUploadStatus(null);
        }, 1500);
      } catch (error) {
        console.error('Upload failed:', error);
        setUploadStatus('error');
      } finally {
        setIsUploading(false);
      }
    },
    [onUploadAccepted, onUploadSuccess]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isUploading,
  });

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-dashed border-gray-600 text-[11px] text-gray-200 hover:border-indigo-500 hover:text-indigo-400 transition-all cursor-pointer"
      >
        <Plus className="w-3 h-3" />
        <span>Add sources</span>
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-[#020617] border border-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-200">Upload Source</h3>
              <button 
                onClick={() => !isUploading && setIsOpen(false)}
                className="p-1 text-gray-500 hover:text-white transition-colors disabled:opacity-30"
                disabled={isUploading}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6">
              <div
                {...getRootProps()}
                className={`
                  border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center transition-all cursor-pointer
                  ${isDragActive ? 'border-indigo-500 bg-indigo-500/5' : 'border-gray-800 bg-gray-900/30'}
                  ${isUploading ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-700 hover:bg-gray-900/50'}
                `}
              >
                <input {...getInputProps()} />
                
                {uploadStatus === 'uploading' ? (
                  <div className="flex flex-col items-center gap-3">
                    <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                    <p className="text-sm text-gray-300">Processing document...</p>
                  </div>
                ) : uploadStatus === 'success' ? (
                  <div className="flex flex-col items-center gap-3">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                    <p className="text-sm text-gray-300">Upload successful!</p>
                  </div>
                ) : uploadStatus === 'error' ? (
                  <div className="flex flex-col items-center gap-3">
                    <X className="w-8 h-8 text-red-500" />
                    <p className="text-sm text-gray-300">Something went wrong. Try again.</p>
                  </div>
                ) : (
                  <>
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 mb-4">
                      <Upload className="w-6 h-6" />
                    </div>
                    <p className="text-sm font-medium text-gray-200 mb-1">
                      {isDragActive ? 'Drop PDF here' : 'Click or drag PDF to upload'}
                    </p>
                    <p className="text-xs text-gray-500">Only PDF files supported (Max 20MB)</p>
                  </>
                )}
              </div>
            </div>

            <div className="p-4 bg-gray-900/50 border-t border-gray-800 flex justify-end">
              <button
                onClick={() => setIsOpen(false)}
                disabled={isUploading}
                className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white disabled:opacity-30"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
