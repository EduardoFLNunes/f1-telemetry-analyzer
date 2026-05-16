import React, { useState, useRef } from 'react'
import { Upload } from 'lucide-react'
import './UploadPanel.css'

function UploadPanel({ title, description, acceptedFormat, onUpload, loading, example }) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const fileInputRef = useRef(null)

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleFile = (file) => {
    if (!file.name.endsWith('.csv')) {
      alert('Por favor, selecione um arquivo CSV')
      return
    }
    
    setSelectedFile(file)
  }

  const handleUploadClick = () => {
    if (selectedFile) {
      onUpload(selectedFile)
    }
  }

  const handleButtonClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="upload-panel">
      <div className="upload-container">
        <h1 className="upload-title">{title}</h1>
        <p className="upload-description">{description}</p>

        <div 
          className={`drop-zone ${dragActive ? 'active' : ''} ${selectedFile ? 'has-file' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={handleButtonClick}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={acceptedFormat}
            onChange={handleChange}
            style={{ display: 'none' }}
          />

          <Upload size={48} className="upload-icon" />
          
          {selectedFile ? (
            <div className="file-selected">
              <p className="file-name">📄 {selectedFile.name}</p>
              <p className="file-size">{(selectedFile.size / 1024).toFixed(2)} KB</p>
            </div>
          ) : (
            <div className="upload-prompt">
              <p className="prompt-main">Arraste o CSV aqui</p>
              <p className="prompt-sub">ou clique para selecionar</p>
            </div>
          )}
        </div>

        {example && (
          <div className="format-example">
            <p className="example-label">Formato esperado:</p>
            <code className="example-code">{example}</code>
          </div>
        )}

        {selectedFile && (
          <button 
            className="btn-upload"
            onClick={handleUploadClick}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="loading-spinner"></div>
                Processando...
              </>
            ) : (
              <>Carregar Arquivo</>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

export default UploadPanel
