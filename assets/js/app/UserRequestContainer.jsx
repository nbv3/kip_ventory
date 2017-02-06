import React, { Component } from 'react'
import $ from "jquery"
import RequestSelectFilter from './RequestSelectFilter'
import RequestList from './RequestList'
import { getCookie } from '../csrf/DjangoCSRFToken'
import { Grid, Row, Col } from 'react-bootstrap'

class UserRequestContainer extends Component {
  constructor(props) {
    super(props);
    this.state = {
      requests:[],
      all_requests:[],
      options: [
                { value: 'O', label: 'Outstanding' },
                { value: 'A', label: 'Approved' },
                { value: 'D', label: 'Denied' },
                { value: 'all', label: 'All' }
            ],
      value: "all",
      placeholder: "Request Types"
    };
    this.setRequests = this.setRequests.bind(this);
    this.setFilter = this.setFilter.bind(this);
    this.deleteRequest = this.deleteRequest.bind(this);

    this.getMyRequests();
  }

  setRequests(requests){
    this.setState({
      requests: requests
    });
  }

  setAllRequests(requests){
    this.setState({
      all_requests: requests
    });
  }

  deleteRequest(request){
    var thisobj = this
    $.ajax({
    url:"/api/requests/" + request.id,
    type: "DELETE",
    beforeSend: function(request) {
      request.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
    },
    success:function(response){
      var newrequests = thisobj.state.requests.filter(req => (req.id != request.id))
      console.log("DELETED SUCCESSFULLY")
      console.log(newrequests)
      thisobj.setState({
        requests: newrequests
      })
    },
    complete:function(){},
    error:function (xhr, textStatus, thrownError){
        alert("error doing something");
        console.log(xhr)
        console.log(textStatus)
        console.log(thrownError)
    }
    });

  }

  setFilter(type){
    this.setState({
      value : type.value,
      requests: this.filterRequests(type.value)
    });
  }


  getMyRequests(){
    var thisobj = this;
    $.getJSON("/api/requests.json", function(data){
      thisobj.setAllRequests(data);
      thisobj.setRequests(data);
    });
  }

  filterRequests(option){
    var new_reqs;
    if(option == "all"){
        new_reqs = this.state.all_requests.slice();
    } else{
        new_reqs = this.state.all_requests.filter(function(request){
          return option == request.status;
        });
    }
    return new_reqs;
  }

  render() {
    return (
      <Grid>
        <Row>
          <Col xs={12} xsOffset={0}>
            <RequestSelectFilter value={this.state.value} placeholder={this.state.placeholder} options={this.state.options} onChange={this.setFilter} />
          </Col>
        </Row>
        <Row>
          <Col xs={12} xsOffset={0}>
            <RequestList deleteRequest={this.deleteRequest} requests={this.state.requests} />
          </Col>
        </Row>
      </Grid>
    );
  }
}


export default UserRequestContainer