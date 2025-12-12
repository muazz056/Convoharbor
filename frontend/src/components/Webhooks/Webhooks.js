import InnerNavbar from '../navbar/InnerNavbar'
import "./Webhooks.css";
import Sidebar from '../Sidebar/Sidebar';
// import ChatWindow from '../ChatWindow/ChatWindow'


  const Webhooks = () => {

    return (
      <>
        <div className="layout-container">
          <Sidebar />
          
          <div className="main-content">
            <InnerNavbar />

          </div>

        </div>
      </>
    );
  };

export default Webhooks;