import React, { useMemo, useState } from 'react';
import './EmbedScriptModal.css';

const EmbedScriptModal = ({ isOpen, onClose, script, chatbotId, publicAppUrl }) => {
  // Hooks must be called unconditionally
  const [activeTab, setActiveTab] = useState('html');

  const snippets = useMemo(() => {
    // Use the script from backend if available, otherwise fall back to template
    const baseEmbed = script || `<!-- Place anywhere inside <body> -->\n<div id="convopilot-widget-container"></div>\n<script>\n  (function(){\n    function ready(fn){\n      if(document.readyState !== 'loading'){ fn(); }\n      else { document.addEventListener('DOMContentLoaded', fn); }\n    }\n\n    ready(function(){\n      var websiteContext = {\n        domain: window.location.hostname,\n        url: window.location.href,\n        path: window.location.pathname,\n        referrer: document.referrer,\n        title: document.title,\n        chatbot_id: ${chatbotId || 'YOUR_CHATBOT_ID'},\n        timestamp: new Date().toISOString()\n      };\n      try {sessionStorage.setItem('convopilot_website_context', JSON.stringify(websiteContext));}catch(e){}\n      var iframe = document.createElement('iframe');\n      iframe.setAttribute('data-convopilot','true');\n      iframe.src = '${publicAppUrl || 'https://your-frontend'}/public/chat/${chatbotId || 'YOUR_CHATBOT_ID'}?website_context=' + encodeURIComponent(JSON.stringify(websiteContext));\n      iframe.style.border = 'none';\n      iframe.style.position = 'fixed';\n      iframe.style.top = '0';\n      iframe.style.left = '0';\n      iframe.style.width = '100%';\n      iframe.style.height = '100%';\n      iframe.style.zIndex = '9999';\n      iframe.style.pointerEvents = 'auto';\n      iframe.style.background = 'transparent';\n      iframe.allow = 'clipboard-write;';\n      (document.getElementById('convopilot-widget-container') || document.body).appendChild(iframe);\n    });\n  })();\n</script>`;
    return {
      html: baseEmbed,
      next: `// app/layout.tsx (App Router)\n'use client'\nimport { useEffect } from 'react'\n\nexport default function RootLayout({ children }: { children: React.ReactNode }) {\n  useEffect(() => {\n    const id = Number(process.env.NEXT_PUBLIC_CHATBOT_ID!);\n    const PUBLIC_URL = process.env.NEXT_PUBLIC_PUBLIC_APP_URL!;\n\n    const ctx = {\n      domain: location.hostname,\n      url: location.href,\n      path: location.pathname,\n      referrer: document.referrer,\n      title: document.title,\n      chatbot_id: id,\n      timestamp: new Date().toISOString()\n    };\n    try { sessionStorage.setItem('convopilot_website_context', JSON.stringify(ctx)); } catch(e) {}\n\n    const mount = document.getElementById('convopilot-widget-container') || (() => {\n      const d = document.createElement('div');\n      d.id = 'convopilot-widget-container';\n      document.body.appendChild(d);\n      return d;\n    })();\n\n    Array.from(mount.querySelectorAll('iframe[data-convopilot]')).forEach(n => n.remove());\n\n    const i = document.createElement('iframe');\n    i.setAttribute('data-convopilot', 'true');\n    i.src = \\\`\\\${PUBLIC_URL}/public/chat/\\\${id}?website_context=\\\${encodeURIComponent(JSON.stringify(ctx))}\\\`;\n    Object.assign(i.style, {\n      border: 'none', position: 'fixed', top: '0', left: '0',\n      width: '100%', height: '100%', zIndex: '9999', pointerEvents: 'auto', background: 'transparent'\n    });\n    i.allow = 'clipboard-write;';\n    mount.appendChild(i);\n\n    return () => i.remove();\n  }, []);\n\n  return <html lang='en'><body>{children}</body></html>;\n}`,
      vue: `// main.ts\nconst id = Number(import.meta.env.VITE_CHATBOT_ID)\nconst PUBLIC_URL = import.meta.env.VITE_PUBLIC_APP_URL as string\n\nconst ctx = {\n  domain: location.hostname,\n  url: location.href,\n  path: location.pathname,\n  referrer: document.referrer,\n  title: document.title,\n  chatbot_id: id,\n  timestamp: new Date().toISOString()\n}\ntry { sessionStorage.setItem('convopilot_website_context', JSON.stringify(ctx)) } catch(e) {}\n\nconst mount = document.getElementById('convopilot-widget-container') || (() => {\n  const d = document.createElement('div'); d.id = 'convopilot-widget-container'; document.body.appendChild(d); return d;\n})()\n\nArray.from(mount.querySelectorAll('iframe[data-convopilot]')).forEach(n => n.remove())\n\nconst i = document.createElement('iframe')\ni.setAttribute('data-convopilot','true')\ni.src = \\\`\\\${PUBLIC_URL}/public/chat/\\\${id}?website_context=\\\${encodeURIComponent(JSON.stringify(ctx))}\\\`\nObject.assign(i.style,{ border:'none', position:'fixed', top:'0', left:'0', width:'100%', height:'100%', zIndex:'9999', pointerEvents:'auto', background:'transparent' })\ni.allow='clipboard-write;'\nmount.appendChild(i)`,
      react: `// App.tsx\nimport { useEffect } from 'react'\n\nexport default function App(){\n  useEffect(()=>{\n    const id = ${chatbotId || 'YOUR_CHATBOT_ID'};\n    const PUBLIC_URL = '${publicAppUrl || 'https://your-frontend'}';\n\n    const ctx = {\n      domain: location.hostname, url: location.href, path: location.pathname,\n      referrer: document.referrer, title: document.title, chatbot_id: id, timestamp: new Date().toISOString()\n    };\n    try { sessionStorage.setItem('convopilot_website_context', JSON.stringify(ctx)); } catch(e) {}\n\n    const mount = document.getElementById('convopilot-widget-container') || (() => {\n      const d = document.createElement('div'); d.id = 'convopilot-widget-container'; document.body.appendChild(d); return d;\n    })();\n\n    Array.from(mount.querySelectorAll('iframe[data-convopilot]')).forEach(n => n.remove());\n\n    const i = document.createElement('iframe');\n    i.setAttribute('data-convopilot','true');\n    i.src = \`\${PUBLIC_URL}/public/chat/\${id}?website_context=\${encodeURIComponent(JSON.stringify(ctx))}\`;\n    Object.assign(i.style,{ border:'none', position:'fixed', top:'0', left:'0', width:'100%', height:'100%', zIndex:'9999', pointerEvents:'auto', background:'transparent' });\n    i.allow = 'clipboard-write;';\n    mount.appendChild(i);\n\n    return ()=> i.remove();\n  },[])\n  return <div/>\n}`,
      woocommerce: baseEmbed,
      shopify: baseEmbed,
      baselinker: baseEmbed,
    };
  }, [script, chatbotId, publicAppUrl]);

  const code = (snippets[activeTab] || snippets.html);

  // --- add how-to and tabs for ecom ---

  if (!isOpen) return null;

  return (
    <div className="embed-modal-backdrop" onClick={onClose}>
      <div className="embed-modal" onClick={e => e.stopPropagation()}>
        <div className="embed-modal-header">
          <h4>Embed Chatbot</h4>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>
        <div className="embed-modal-body">
          <div className="tabs">
            <button className={`tab ${activeTab==='html'?'active':''}`} onClick={()=>setActiveTab('html')}>HTML</button>
            <button className={`tab ${activeTab==='next'?'active':''}`} onClick={()=>setActiveTab('next')}>Next.js</button>
            <button className={`tab ${activeTab==='vue'?'active':''}`} onClick={()=>setActiveTab('vue')}>Vue 3</button>
            <button className={`tab ${activeTab==='react'?'active':''}`} onClick={()=>setActiveTab('react')}>React</button>
            <button className={`tab ${activeTab==='woocommerce'?'active':''}`} onClick={()=>setActiveTab('woocommerce')}>WooCommerce</button>
            <button className={`tab ${activeTab==='shopify'?'active':''}`} onClick={()=>setActiveTab('shopify')}>Shopify</button>
            <button className={`tab ${activeTab==='baselinker'?'active':''}`} onClick={()=>setActiveTab('baselinker')}>BaseLinker</button>
          </div>

          <div className="howto">
            {activeTab==='html' && (<p>Place the container and script anywhere inside &lt;body&gt;. It will add a full-screen iframe with website context.</p>)}
            {activeTab==='next' && (<p>Add this in a client component (app/layout.tsx or pages/_app.tsx). It runs only on the client and appends the iframe.</p>)}
            {activeTab==='vue' && (<p>Put this in main.ts or a root component mounted hook. It appends the iframe and persists context to sessionStorage.</p>)}
            {activeTab==='react' && (<p>Use inside useEffect so it runs in the browser after mount. A container div will be created if missing.</p>)}
            {activeTab==='woocommerce' && (<>
              <p><strong>WooCommerce:</strong> Add this script to your <b>theme's footer (footer.php)</b>, <b>Theme Customizer {'>'} Custom HTML</b>, or via a plugin such as <b>WPCode, Code Snippets, or Insert Headers and Footers</b>. Place it before the closing <code>&lt;/body&gt;</code> tag.</p>
            </>)}
            {activeTab==='shopify' && (<>
              <p><strong>Shopify:</strong> In Shopify admin, go to <b>Online Store → Themes → Edit Code</b>. Open <b>layout/theme.liquid</b> and paste this code right before the closing <code>&lt;/body&gt;</code> tag. Save and publish your theme.</p>
            </>)}
            {activeTab==='baselinker' && (<>
              <p><strong>BaseLinker:</strong> Go to <b>Integrations → Additional Scripts/Custom HTML</b> in your BaseLinker admin, and paste this code. It will embed the chat widget on your e-commerce site.</p>
            </>)}
          </div>

          <pre className="code-block"><code>{code}</code></pre>
        </div>
        <div className="embed-modal-footer">
          <button className="copy-btn" onClick={()=>{
            navigator.clipboard.writeText(code);
            alert('Copied to clipboard!');
          }}>Copy</button>
          <button className="close-btn secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default EmbedScriptModal;
