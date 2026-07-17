import React, { useState, useEffect, useRef } from 'react';
import { UploadCloud, Search, Database, FileSpreadsheet, AlertCircle, FileJson, Loader2 } from 'lucide-react';

export function DatasetExplorer() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [keyword, setKeyword] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/datasets');
      const json = await res.json();
      setDatasets(json.datasets || []);
    } catch (err) {
      console.error('Failed to fetch datasets:', err);
    }
  };

  const handleSearch = async (pageNum = 1) => {
    if (!selectedDataset) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/datasets/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: selectedDataset,
          keyword: keyword,
          page: pageNum,
          page_size: 50
        })
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to search dataset');
      }
      const json = await res.json();
      setData(json);
      setPage(json.page);
      setTotalPages(json.total_pages);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedDataset) {
      handleSearch(1);
    } else {
      setData(null);
    }
  }, [selectedDataset]);

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/datasets/upload', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Upload failed');
      }
      await fetchDatasets();
      setSelectedDataset(file.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const renderTable = () => {
    if (!data || !data.columns) return null;
    if (data.data.length === 0) {
      return (
        <div className="text-center py-10 text-gray-500">
          No records found matching "{keyword}".
        </div>
      );
    }

    return (
      <div className="overflow-x-auto rounded-md border border-gray-800 bg-[#0c0c0e]">
        <table className="w-full text-sm text-left text-gray-300">
          <thead className="text-xs text-gray-400 uppercase bg-gray-900 border-b border-gray-800">
            <tr>
              {data.columns.map(col => (
                <th key={col} className="px-4 py-3 font-medium truncate max-w-[200px]" title={col}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.data.map((row, i) => (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                {data.columns.map(col => (
                  <td key={`${i}-${col}`} className="px-4 py-3 truncate max-w-[200px]" title={String(row[col])}>
                    {String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col p-6 max-w-[1600px] mx-auto w-full gap-6">
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Database className="w-6 h-6 text-blue-500" />
            Dataset Explorer
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Upload and search tabular data for open-source intelligence.
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload}
            className="hidden" 
            accept=".csv,.xlsx,.xls,.json" 
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md flex items-center gap-2 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
            {uploading ? 'Uploading...' : 'Upload Dataset'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Sidebar / Controls */}
        <div className="md:col-span-1 flex flex-col gap-4">
          <div className="bg-[#111113] border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wider">Available Datasets</h3>
            {datasets.length === 0 ? (
              <p className="text-sm text-gray-500 italic">No datasets available. Please upload one.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {datasets.map(ds => (
                  <button
                    key={ds.id}
                    onClick={() => setSelectedDataset(ds.id)}
                    className={`flex items-center gap-2 text-left p-2 rounded-md text-sm transition-colors ${selectedDataset === ds.id ? 'bg-blue-900/30 text-blue-400 border border-blue-800/50' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200 border border-transparent'}`}
                  >
                    {ds.name.endsWith('.csv') || ds.name.endsWith('.xlsx') ? (
                      <FileSpreadsheet className="w-4 h-4 shrink-0" />
                    ) : (
                      <FileJson className="w-4 h-4 shrink-0" />
                    )}
                    <span className="truncate" title={ds.name}>{ds.name}</span>
                    <span className="text-[10px] text-gray-600 ml-auto">{ds.size_mb} MB</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Main Content Area */}
        <div className="md:col-span-3 flex flex-col gap-4 flex-1">
          {error && (
            <div className="bg-red-900/20 border border-red-900/50 text-red-400 p-3 rounded-md flex items-center gap-2 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          {!selectedDataset ? (
            <div className="flex-1 border border-dashed border-gray-800 rounded-lg flex flex-col items-center justify-center p-12 text-gray-500 bg-[#111113]/50 min-h-[400px]">
              <Database className="w-12 h-12 mb-4 opacity-50" />
              <p>Select a dataset from the sidebar or upload a new one to begin exploring.</p>
            </div>
          ) : (
            <>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    type="text"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch(1)}
                    placeholder="Search keywords in dataset..."
                    className="w-full bg-[#111113] border border-gray-800 rounded-md pl-10 pr-4 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
                <button
                  onClick={() => handleSearch(1)}
                  disabled={loading}
                  className="bg-gray-800 hover:bg-gray-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
                >
                  Search
                </button>
              </div>

              {loading ? (
                <div className="flex-1 flex items-center justify-center py-20 min-h-[400px]">
                  <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  {data && (
                    <div className="flex justify-between items-center text-sm text-gray-400">
                      <span>Found {data.total_records.toLocaleString()} rows</span>
                      <div className="flex items-center gap-4">
                        <span>Page {page} of {totalPages}</span>
                        <div className="flex gap-1">
                          <button 
                            disabled={page <= 1}
                            onClick={() => handleSearch(page - 1)}
                            className="px-2 py-1 bg-gray-800 rounded hover:bg-gray-700 disabled:opacity-50"
                          >
                            Prev
                          </button>
                          <button 
                            disabled={page >= totalPages}
                            onClick={() => handleSearch(page + 1)}
                            className="px-2 py-1 bg-gray-800 rounded hover:bg-gray-700 disabled:opacity-50"
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                  {renderTable()}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
