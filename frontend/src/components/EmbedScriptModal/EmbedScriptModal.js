import React, { useMemo, useState } from 'react';
import './EmbedScriptModal.css';

const EmbedScriptModal = ({ isOpen, onClose, script, chatbotId, publicAppUrl }) => {
  // Hooks must be called unconditionally
  const [activeTab, setActiveTab] = useState('html');

  const snippets = useMemo(() => {
    // Use the script from backend if available, otherwise fall back to template
    const baseEmbed = script || `<!-- Place anywhere inside <body> -->\n<div id="convoharbor-widget-container"></div>\n<script>\n  (function(){\n    function ready(fn){\n      if(document.readyState !== 'loading'){ fn(); }\n      else { document.addEventListener('DOMContentLoaded', fn); }\n    }\n\n    ready(function(){\n      var websiteContext = {\n        domain: window.location.hostname,\n        url: window.location.href,\n        path: window.location.pathname,\n        referrer: document.referrer,\n        title: document.title,\n        chatbot_id: ${chatbotId},\n        timestamp: new Date().toISOString()\n      };\n      try {sessionStorage.setItem('convoharbor_website_context', JSON.stringify(websiteContext));}catch(e){}\n      var iframe = document.createElement('iframe');\n      iframe.setAttribute('data-convoharbor','true');\n      iframe.src = '${publicAppUrl}/public/chat/${chatbotId}?website_context=' + encodeURIComponent(JSON.stringify(websiteContext));\n      iframe.style.border = 'none';\n      iframe.style.outline = 'none';\n      iframe.style.position = 'fixed';\n      iframe.style.bottom = '0';\n      iframe.style.right = '0';\n      iframe.style.width = '400px';\n      iframe.style.height = '620px';\n      iframe.style.maxWidth = '100vw';\n      iframe.style.maxHeight = '100vh';\n      iframe.style.zIndex = '9999';\n      iframe.style.background = 'transparent';\n      iframe.style.pointerEvents = 'auto';\n      iframe.allow = 'clipboard-write;';\n      (document.getElementById('convoharbor-widget-container') || document.body).appendChild(iframe);\n    });\n  })();\n</script>`;

    return {
      html: baseEmbed,
      next: `// components/ConvoharborWidget.tsx (create this file)\n// Chatbot ID: ${chatbotId}\n// Frontend URL: ${publicAppUrl}\n'use client';\nimport { useEffect } from 'react';\n\nexport default function ConvoharborWidget() {\n  useEffect(() => {\n    const id = ${chatbotId};\n    const PUBLIC_URL = '${publicAppUrl}';\n\n    const ctx = {\n      domain: location.hostname,\n      url: location.href,\n      path: location.pathname,\n      referrer: document.referrer,\n      title: document.title,\n      chatbot_id: id,\n      timestamp: new Date().toISOString()\n    };\n    try { sessionStorage.setItem('convoharbor_website_context', JSON.stringify(ctx)); } catch(e) {}\n\n    const mount = document.getElementById('convoharbor-widget-container') || (() => {\n      const d = document.createElement('div');\n      d.id = 'convoharbor-widget-container';\n      document.body.appendChild(d);\n      return d;\n    })();\n\n    Array.from(mount.querySelectorAll('iframe[data-convoharbor]')).forEach(n => n.remove());\n\n    const i = document.createElement('iframe');\n    i.setAttribute('data-convoharbor', 'true');\n    i.src = \`\${PUBLIC_URL}/public/chat/\${id}?website_context=\${encodeURIComponent(JSON.stringify(ctx))}\`;\n    Object.assign(i.style, {\n      border: 'none', outline: 'none', position: 'fixed',\n      zIndex: '9999', pointerEvents: 'auto', background: 'transparent'\n    });\n    i.style.width = '400px';\\n    i.style.height = '620px';\\n    i.style.maxWidth = '100vw';\\n    i.style.maxHeight = '100vh';\\n    i.style.bottom = '0';\\n    i.style.right = '0';\\n    i.allow = 'clipboard-write;';\\n    mount.appendChild(i);\\n\\n    return () => { i.remove(); };\n  }, []);\n\n  return null;\n}\n\n// ── Then in app/layout.tsx, import and render it: ──\n// import ConvoharborWidget from '@/components/ConvharborWidget';\n//\n// export default function RootLayout({ children }) {\n//   return (\n//     <html lang='en'>\n//       <body>\n//         {children}\n//         <ConvharborWidget />\n//       </body>\n//     </html>\n//   );\n// }`,
      vue: `// Create a plugin file, e.g. plugins/convoharbor.ts\n// Chatbot ID: ${chatbotId}\n// Frontend URL: ${publicAppUrl}\nimport { defineNuxtPlugin } from '#app';\n\nexport default defineNuxtPlugin(() => {\n  if (process.client) {\n    const id = ${chatbotId};\n    const PUBLIC_URL = '${publicAppUrl}';\n\n    const ctx = {\n      domain: location.hostname,\n      url: location.href,\n      path: location.pathname,\n      referrer: document.referrer,\n      title: document.title,\n      chatbot_id: id,\n      timestamp: new Date().toISOString()\n    };\n    try { sessionStorage.setItem('convoharbor_website_context', JSON.stringify(ctx)); } catch(e) {}\n\n    const mount = document.getElementById('convoharbor-widget-container') || (() => {\n      const d = document.createElement('div'); d.id = 'convoharbor-widget-container'; document.body.appendChild(d); return d;\n    })();\n\n    Array.from(mount.querySelectorAll('iframe[data-convoharbor]')).forEach(n => n.remove());\n\n    const i = document.createElement('iframe');\n    i.setAttribute('data-convoharbor', 'true');\n    i.src = \`\${PUBLIC_URL}/public/chat/\${id}?website_context=\${encodeURIComponent(JSON.stringify(ctx))}\`;\n    Object.assign(i.style, {\n      border: 'none', outline: 'none', position: 'fixed',\n      zIndex: '9999', pointerEvents: 'auto', background: 'transparent'\n    });\n    i.style.width = '400px';\\n    i.style.height = '620px';\\n    i.style.maxWidth = '100vw';\\n    i.style.maxHeight = '100vh';\\n    i.style.bottom = '0';\\n    i.style.right = '0';\\n    i.allow = 'clipboard-write;';\\n    mount.appendChild(i);\n  }\n});`,
      react: `// components/ConvharborWidget.jsx (create this file)\nimport { useEffect } from 'react';\n\nexport default function ConvharborWidget() {\n  useEffect(() => {\n    const id = ${chatbotId};\n    const PUBLIC_URL = '${publicAppUrl}';\n\n    const ctx = {\n      domain: location.hostname, url: location.href, path: location.pathname,\n      referrer: document.referrer, title: document.title, chatbot_id: id, timestamp: new Date().toISOString()\n    };\n    try { sessionStorage.setItem('convoharbor_website_context', JSON.stringify(ctx)); } catch(e) {}\n\n    const mount = document.getElementById('convoharbor-widget-container') || (() => {\n      const d = document.createElement('div'); d.id = 'convoharbor-widget-container'; document.body.appendChild(d); return d;\n    })();\n\n    Array.from(mount.querySelectorAll('iframe[data-convoharbor]')).forEach(n => n.remove());\n\n    const i = document.createElement('iframe');\n    i.setAttribute('data-convoharbor','true');\n    i.src = \`\${PUBLIC_URL}/public/chat/\${id}?website_context=\${encodeURIComponent(JSON.stringify(ctx))}\`;\n    Object.assign(i.style,{ border:'none', outline:'none', position:'fixed', zIndex:'9999', pointerEvents:'auto', background:'transparent' });\n    i.style.width = '400px';\\n    i.style.height = '620px';\\n    i.style.maxWidth = '100vw';\\n    i.style.maxHeight = '100vh';\\n    i.style.bottom = '0';\\n    i.style.right = '0';\\n    i.allow = 'clipboard-write;';\\n    mount.appendChild(i);\\n\\n    return () => { i.remove(); };\n  },[]);\n\n  return null;\n}\n\n// ── Then in App.jsx, import and render it: ──\n// import ConvharborWidget from './components/ConvharborWidget';\n//\n// export default function App() {\n//   return (\n//     <div>\n//       ...your app...\n//       <ConvharborWidget />\n//     </div>\n//   );\n// }`,
      woocommerce: baseEmbed,
      shopify: baseEmbed,
      baselinker: baseEmbed,
    };
  }, [script, chatbotId, publicAppUrl]);

  const code = (snippets[activeTab] || snippets.html);

  const aiPrompts = {
    html: "Add this script tag inside the <body> of your HTML page. The widget will load as a floating chat button.",
    next: "Create a new file components/ConvharborWidget.tsx with the code below, then import <ConvharborWidget /> in your app/layout.tsx inside <body>. No env vars needed — the chatbot ID and frontend URL are baked directly into the script.",
    vue: "Create plugins/convoharbor.ts (Nuxt) or copy the code into main.ts (Vue CLI/Vite). No env vars needed — the chatbot ID and frontend URL are baked directly into the script.",
    react: "Create components/ConvharborWidget.jsx with the code below, then import <ConvharborWidget /> in your app's root component. The widget renders nothing visible — it creates the iframe via useEffect.",
    woocommerce: "Paste this code before the closing </body> in your theme's footer.php, or use a plugin like WPCode. No additional setup needed.",
    shopify: "In Shopify admin, go to Online Store > Themes > Edit Code. Open layout/theme.liquid and paste before </body>. No env vars needed — the chatbot ID is baked into the script.",
    baselinker: "Go to Integrations > Additional Scripts/Custom HTML in your BaseLinker admin and paste this code. It will embed the widget across your store.",
  };

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

          <div className="embed-ai-prompt">
            <strong>AI Assistant Prompt</strong>
            <p>{aiPrompts[activeTab] || aiPrompts.html}</p>
          </div>

          <div className="howto">
            {activeTab==='html' && (<p>Place the container and script anywhere inside &lt;body&gt;. It will add a widget-sized iframe positioned based on admin theme config.</p>)}
            {activeTab==='next' && (<p>Create <code>components/ConvharborWidget.tsx</code> with the code below, then import and render <code>&lt;ConvharborWidget /&gt;</code> in <code>app/layout.tsx</code> inside <code>&lt;body&gt;</code>.</p>)}
            {activeTab==='vue' && (<p>Create <code>plugins/convoharbor.ts</code> (Nuxt 3) or paste into <code>main.ts</code> (Vue CLI/Vite). Wrap with <code>process.client</code> check if using Nuxt.</p>)}
            {activeTab==='react' && (<p>Create <code>components/ConvharborWidget.jsx</code> with the code below, then render <code>&lt;ConvharborWidget /&gt;</code> in your root component.</p>)}
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
