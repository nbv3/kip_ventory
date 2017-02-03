import React, { Component } from 'react'
import { ListGroup, ListGroupItem, Label } from 'react-bootstrap'



class RequestList extends Component{
  constructor(props) {
    super(props);
    this.state = {
      requests: [],
    };

  };


  render(){
    var list = [];

    this.props.requests.forEach(function(request){
      var label = null;
      if(request.status=="O") {
        var label = <Label className="pull-right" bsStyle="warning">Outstanding</Label>
      }
      if(request.status=="A") {
        var label = <Label className="pull-right" bsStyle="success">Approved</Label>
      }
      if(request.status=="D") {
        var label = <Label className="pull-right" bsStyle="danger">Denied</Label>
      }

      if(label == null){
        console.log("Label equals null for " + request.status);
      }
      list.push(<ListGroupItem><b>Item:</b> {request.item.name}   <b>Quantity:</b> {request.quantity}        <b>Opened:</b> {request.date_open.substring(0,9)} {label}</ListGroupItem>)
    });
    return(
      <ListGroup>
        {list}
      </ListGroup>
    )
  }

}

export default RequestList