import InnerNavbar from '../navbar/InnerNavbar'
import "./Leads&Contacts.css";
import Sidebar from '../Sidebar/Sidebar';
// import ChatWindow from '../ChatWindow/ChatWindow'


  const Leads_Contacts = () => {

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

export default Leads_Contacts;