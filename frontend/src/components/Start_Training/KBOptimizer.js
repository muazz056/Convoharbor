import InnerNavbar from '../navbar/InnerNavbar'
import '../Sidebar/Sidebar.css'; 
import { Link } from 'react-router-dom';

  const KBOptimizer = () => {

    return (
      <>
        <InnerNavbar />
           <div className="d-flex">
              {/* SIDE BAR */}
              <div className="sidebar d-flex flex-column align-items-start p-3 bg-light">
                <span className="badge bg-success mb-3">$ Free Plan</span>
          
                {/* My Bot with Image + Dropdown */}
                <div className="position-relative w-100 mb-2">
                  <Link to="/chatbot/training/website" className="sidebar-button w-100 text-start d-flex align-items-center">
                    <i class="fas fa-globe me-2"></i> Website
                  </Link>
                </div>
          
                {/* Copy Text Icon */}
                <Link to="/chatbot/training/files" className="sidebar-button mb-2 w-100 text-start d-flex align-items-center">
                  <i class="fas fa-file-lines me-2"></i> Files
                </Link>
          
                {/* GPT MINI */}
                <Link to="/chatbot/training/question_answer" className="sidebar-button mb-2 w-100 text-start"><i class="fas fa-circle-question me-2"></i>Question & Answer</Link>
          
                {/* Start Training with Brain Icon */}
                <Link to="/chatbot/training/text" className="sidebar-button mb-2 w-100 text-start d-flex align-items-center">
                  <i class="fas fa-font me-2"></i>Text
                </Link>
           
                {/* Share Chatbot with Dropdown */}
                <div className="position-relative w-100 mb-2">
                  <Link to="/chatbot/training/corrections" className="sidebar-button w-100 text-start d-flex align-items-center">
                    <i class="fas fa-square-check me-2"></i> Corrections
                  </Link>
                </div>
          
                <Link to="/chatbot/training/knowledgeBaseOptimzer" className="btn gradient-btn mt-auto w-100">
                Knowledge base optimizer
                </Link>

              </div>
              {/* END SIDE BAR */}
            
            {/* CHAT WINDOW */}
                <div className="chat-window">
                   <div className='mt-2'>
                   <div className='bg-dark text-light p-3 rounded'>Knowledge base optimizer</div>
                   <div className='h-100 p-5'>
                      <b>Understand which sources are used</b>
                      <br />
                      Type a message to see which sources are used to respond. This allows for adding new sources or 
                      improving existing ones to make the bot more efficient.
                   </div>
                    <div className="chat-input-box d-flex align-items-center p-2 mt-4 bg-light border mx-5 mt-5">

                      <input type="text" className="form-control border-0 bg-light" placeholder="type your message here.." />
                      
                      <button className="send-btn">
                        <i className="fas fa-arrow-up"></i>
                      </button>
                    
                    </div>
                  </div>

                </div>
            {/* END CHAT WINDOW */}

      </div>
      </>
    );
  };

export default KBOptimizer;