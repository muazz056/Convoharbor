import '../ChatWindow/ChatWindow.css'

const ChatWindow = () => {
  return (
    <div className="chat-window mt-5">
      <div className="text-center px-5"> 
        <h2>
          <span className="main-gradient-text">How can we assist you today?</span>
        </h2>
        <p className="text-muted px-5">
          Get expert guidance powered by AI agents specializing in Sales, Marketing, and Negotiation. Choose the agent that suits your needs and start your conversation with ease.
        </p>
      </div>

      <div className="chat-input-box d-flex align-items-center p-2 mt-4 bg-light border mx-5 mt-5">
        
        <button className="attachment-button"><i className="fas fa-paperclip fa-lg"></i></button>

        <input type="text" className="form-control border-0 bg-light" placeholder="type your message here.." />
        
        <button className="bg-light border-0"><i className="fas fa-2x text-muted fa-microphone mx-2"></i></button>
        
        <button className="send-btn">
          <i className="fas fa-arrow-up"></i>
        </button>
      
      </div>

    </div>
  );
};

export default ChatWindow;