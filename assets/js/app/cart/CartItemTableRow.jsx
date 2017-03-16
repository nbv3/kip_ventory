import React from 'react'
import { Grid, Row, Col, Button, Panel, FormGroup, FormControl, Glyphicon, OverlayTrigger, Popover} from 'react-bootstrap'
import { browserHistory } from 'react-router'
import ItemTableDetail from '../inventory/ItemTableDetail'
import { ajax } from 'jquery'
import { getCookie } from '../../csrf/DjangoCSRFToken'



const CartItemTableRow = React.createClass({

  getInitialState() {
    return {
      item: this.props.cartItem.item,
      request_type: this.props.cartItem.request_type,
      quantity: this.props.cartItem.quantity,
    }
  },


  handleQuantityChange(e) {
    var q = Number(e.target.value)
    if (q > this.state.item.quantity) {
      e.stopPropagation()
    } else {
      this.setState({quantity: Number(e.target.value)}, this.updateCartItem)
    }
  },

  handleRequestTypeChange(e) {
    this.setState({request_type: e.target.value}, this.updateCartItem)
  },

  updateCartItem() {
    var url = "/api/cart/" + this.state.item.name + "/"
    var _this = this
    var data = {
      quantity: this.state.quantity,
      request_type: this.state.request_type
    }
    ajax({
      url: url,
      type: "PUT",
      contentType: "application/json",
      data: JSON.stringify({
        quantity: this.state.quantity,
        request_type: this.state.request_type
      }),
      beforeSend: function(request) {
        request.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
      },
      success:function(response){},
      complete:function(){},
      error:function (xhr, textStatus, thrownError){console.log(xhr)}
    })
  },

  deleteCartItem() {
    var url = "/api/cart/" + this.state.item.name + "/"
    var _this = this
    ajax({
      url: url,
      type: "DELETE",
      beforeSend: function(request) {
        request.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
      },
      success:function(response){},
      complete:function(){},
      error:function (xhr, textStatus, thrownError){console.log(xhr)}
    });
  },

  getPopover() {
    return (
      <Popover style={{maxWidth:"200px"}} id="tag-popover">
        <Col sm={12}>
          <div style={{fontSize:"10px"}}>
            <p>{this.state.item.tags.join(', ')}</p>
          </div>
        </Col>
      </Popover>
    )
  },

  render() {
    return (
      <tr>
        <td data-th="Item Information">
          <ItemTableDetail item={this.state.item} />
        </td>
        <td data-th="Model No." className="text-center">{this.state.item.model_no}</td>
        <td data-th="Available" className="text-center">{this.state.item.quantity}</td>
        <td data-th="Tags" className="text-left">
          <OverlayTrigger rootClose trigger="click" placement="right" overlay={this.getPopover()}>
            <Glyphicon glyph="tags" className="clickable" onClick={(e) => this.setState({showTags: true})}/>
          </OverlayTrigger>
        </td>
        <td className="text-center">
          <a href="" style={{color: "#5bc0de"}} onClick={this.deleteCartItem}>Delete</a>
        </td>
        <td data-th="Request Type" className="text-center">
            <FormControl className="text-center"
                         style={{fontSize:"10px", height:"30px", lineHeight:"30px"}}
                         componentClass="select"
                         name="request_type"
                         value={this.state.request_type}
                         onChange={this.handleRequestTypeChange}>
              <option value="disbursement">Disbursement</option>
              <option value="loan">Loan</option>
            </FormControl>
        </td>
        <td />
        <td data-th="Quantity">
          <FormGroup bsSize="small" style={{margin:"auto"}}>
            <FormControl type="number"
                         className="text-center"
                         name="quantity"
                         min={1} step={1} max={this.state.item.quantity}
                         value={this.state.quantity}
                         onChange={this.handleQuantityChange} />
          </FormGroup>
        </td>
      </tr>
      )
    }
});

export default CartItemTableRow
