import InnerNavbar from '../navbar/InnerNavbar'
import '../Sidebar/Sidebar.css'; 
import { Link } from 'react-router-dom';

  const Website = () => {

    return (
      <>
        <InnerNavbar />
           <div className="d-flex">
              {/* SIDE BAR */}
              <div className="sidebar d-flex flex-column align-items-start p-3 bg-light">
                <span className="badge bg-success mb-3">$ Free Plan</span>
          
                {/* My Bot with Image + Dropdown */}
                <div className="position-relative w-100 mb-2">
                  <Link to="/chatbot/training/website" className="sidebar-button-selected w-100 text-start d-flex align-items-center">
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
                  <button className="btn gradient-btn"><i class="fas fa-plus"></i> Add new website</button>
                   <div className='mt-2'>
                   <div className='bg-dark text-light p-3 rounded'>Website Sources</div>
                   <div className='h-100 text-center p-5'>
                      No trainings in this category yet
                   </div>
                  </div>

                </div>
            {/* END CHAT WINDOW */}

      </div>
      </>
    );
  };

export default Website;