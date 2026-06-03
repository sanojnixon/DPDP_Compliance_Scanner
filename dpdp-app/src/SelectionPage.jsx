import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import DarkModeToggle from './DarkModeToggle';
import DevModeToggle from './DevModeToggle';

export default function SelectionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [images, setImages] = useState([]);
  // locationImageIds is used only for the initial fetch filter.
  // For navigation, we always use `liveImageIds` derived from the actual DB response.
  const locationImageIds = location.state?.imageIds || [];

  // Derive live IDs from what the DB actually has — avoids passing dead IDs
  // that were deleted from the DB after a previous scan.
  const liveImageIds = images.map(img => img.id);

  const fetchImages = async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/');
      return;
    }
    try {
      // If we have specific IDs from location state, filter by them.
      // Otherwise fetch all images for this user.
      const queryParam = locationImageIds.length > 0 ? `?ids=${locationImageIds.join(',')}` : '';
      const res = await fetch(`http://localhost:5000/api/images${queryParam}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setImages(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchImages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);



  const deleteImage = async (id) => {
    const token = localStorage.getItem('token');
    try {
      const res = await fetch(`http://localhost:5000/api/images/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setImages(images.filter(img => img.id !== id));
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <>
      {/* SIBerNet Style Header */}
      <header className="w-full bg-sib-maroon flex-shrink-0 z-10 shadow-sm">
        <div className="max-w-[1200px] mx-auto flex items-center justify-between px-5" style={{ height: '90px' }}>
          <img
            src="/SIB_Logo.png"
            alt="South Indian Bank"
            className="w-auto object-contain cursor-pointer"
            style={{ height: '71.5px' }}
            onClick={() => navigate('/')}
            onError={e => { e.currentTarget.style.display = 'none' }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <DarkModeToggle />
            <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.18)', borderRadius: '1px' }} />
            <DevModeToggle />
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden relative bg-[#F9FAFB]">
        {/* Decorative background elements matching login page */}
        <div className="absolute top-[-10%] left-[-5%] w-[40vw] h-[40vw] rounded-full bg-red-50/50 blur-3xl z-0 pointer-events-none"></div>
        <div className="absolute bottom-[-10%] right-[-5%] w-[30vw] h-[30vw] rounded-full bg-gray-200/50 blur-3xl z-0 pointer-events-none"></div>
        
        <main className="flex-1 flex px-4 py-8 max-w-[1400px] mx-auto w-full gap-8 relative z-10">
          
          {/* Left Sidebar: Image Preview Panel */}
          <aside className="w-[320px] flex-shrink-0 bg-white rounded-2xl shadow-card p-5 flex flex-col h-[calc(100vh-180px)] border border-gray-100">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
              <h3 className="text-[16px] font-display font-bold text-gray-900">Uploaded Documents</h3>
              <span className="bg-red-50 text-sib-maroon text-xs font-bold px-2 py-1 rounded-full">{images.length}</span>
            </div>
            
            <div className="flex-1 overflow-y-auto pr-2 space-y-4 custom-scrollbar">
              {images.map(img => (
                <div key={img.id} className="relative group rounded-xl border border-gray-200 overflow-hidden bg-gray-50 shadow-sm hover:shadow-md transition-shadow">
                   <button 
                    onClick={() => deleteImage(img.id)} 
                    className="absolute top-2 right-2 bg-white/90 text-red-500 p-1.5 rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-500 hover:text-white transition-all z-10 shadow-sm"
                    title="Delete image"
                   >
                     <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                   </button>
                   <div className="h-[140px] w-full bg-gray-200 relative overflow-hidden">
                     <img src={img.data} alt={img.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                   </div>
                   <div className="p-3 bg-white">
                     <p className="text-[13px] font-medium text-gray-800 truncate" title={img.name}>{img.name}</p>
                     <p className="text-[11px] text-gray-400 mt-0.5">{new Date(img.uploaded_at).toLocaleString()}</p>
                   </div>
                </div>
              ))}
              {images.length === 0 && (
                <div className="h-full flex flex-col items-center justify-center text-center p-4">
                  <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-400"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                  </div>
                  <p className="text-[14px] font-medium text-gray-600">No images found</p>
                  <p className="text-[12px] text-gray-400 mt-1">Uploaded images will appear here.</p>
                </div>
              )}
            </div>
            
            <div className="mt-4 pt-4 border-t border-gray-100">
               <button onClick={() => navigate('/upload')} className="w-full py-2.5 px-4 bg-white border border-gray-200 text-gray-700 text-sm font-semibold rounded-xl hover:bg-gray-50 transition-colors flex items-center justify-center gap-2">
                 <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                 Upload More
               </button>
            </div>
          </aside>

          {/* Right Area: Tools Selection */}
          <div className="flex-1 flex flex-col justify-center max-w-[900px] ml-4">
            
            <div className="mb-10 text-left stagger-l">
              <span className="inline-block px-4 py-1.5 rounded-full bg-red-50 text-sib-maroon text-[11px] font-bold tracking-widest uppercase mb-4 border border-red-100">
                Analysis Tools
              </span>
              <h1 className="text-[32px] font-display text-gray-900 font-bold mb-3 tracking-tight">Select an Audit Module</h1>
              <p className="text-[15px] text-gray-500 font-normal max-w-[600px] leading-relaxed">
                Choose the analysis tool to run against your uploaded document. Our AI engines will process the image and generate a comprehensive report.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full stagger-r">
              
              {/* DPDP Compliance Card */}
              <div
                className="group cursor-pointer bg-white rounded-2xl shadow-card hover:shadow-[0_20px_40px_rgba(176,30,35,0.08)] transition-all duration-300 border border-transparent hover:border-sib-maroon/20 overflow-hidden flex flex-col h-[280px]"
                onClick={() => navigate('/dpdp/process', { state: { imageIds: liveImageIds } })}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && navigate('/dpdp/process', { state: { imageIds: liveImageIds } })}
                id="dpdp-compliance-card"
              >
                <div className="h-1.5 w-full bg-gradient-to-r from-[#C8282E] to-[#8A1519]"></div>
                <div className="p-8 flex flex-col h-full">
                  <div className="w-12 h-12 rounded-xl bg-red-50 flex items-center justify-center text-sib-maroon mb-5 group-hover:scale-110 transition-transform duration-300">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    </svg>
                  </div>
                  <h2 className="text-[20px] font-display font-bold text-gray-900 mb-2 group-hover:text-sib-maroon transition-colors duration-200">
                    DPDP Compliance
                  </h2>
                  <p className="text-[13px] text-gray-500 leading-relaxed mb-6 flex-1">
                    Scan the document for PII and ensure it meets Digital Personal Data Protection Act requirements.
                  </p>
                  <div className="flex items-center text-sib-maroon font-semibold text-[12px] tracking-wide uppercase">
                    Launch Scanner
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="ml-2 group-hover:translate-x-1 transition-transform">
                      <path d="M5 12h14M12 5l7 7-7 7"/>
                    </svg>
                  </div>
                </div>
              </div>

              {/* Accessibility Auditor Card */}
              <div className="group cursor-pointer bg-white rounded-2xl shadow-card hover:shadow-[0_20px_40px_rgba(176,30,35,0.08)] transition-all duration-300 border border-transparent hover:border-sib-maroon/20 overflow-hidden flex flex-col h-[280px]">
                <div className="h-1.5 w-full bg-gray-200 group-hover:bg-gradient-to-r group-hover:from-gray-400 group-hover:to-gray-600 transition-all duration-300"></div>
                <div className="p-8 flex flex-col h-full">
                  <div className="w-12 h-12 rounded-xl bg-gray-50 flex items-center justify-center text-gray-600 mb-5 group-hover:scale-110 group-hover:bg-gray-100 transition-all duration-300">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M12 16v-4"/>
                      <path d="M12 8h.01"/>
                    </svg>
                  </div>
                  <h2 className="text-[20px] font-display font-bold text-gray-900 mb-2 group-hover:text-gray-700 transition-colors duration-200">
                    Accessibility Auditor
                  </h2>
                  <p className="text-[13px] text-gray-500 leading-relaxed mb-6 flex-1">
                    Analyze UI contrast ratios, structure, and readability to ensure compliance with WCAG guidelines.
                  </p>
                  <div className="flex items-center text-gray-600 font-semibold text-[12px] tracking-wide uppercase">
                    Launch Auditor
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="ml-2 group-hover:translate-x-1 transition-transform">
                      <path d="M5 12h14M12 5l7 7-7 7"/>
                    </svg>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </main>
      </div>

      <footer className="w-full bg-[#2F2F2F] py-3 flex-shrink-0 relative z-10">
        <div className="max-w-[1200px] mx-auto px-5 flex items-center justify-between">
          <p className="text-white/35 text-[11px] font-medium">&copy; 2026 South Indian Bank. All rights reserved.</p>
        </div>
      </footer>
    </>
  );
}
