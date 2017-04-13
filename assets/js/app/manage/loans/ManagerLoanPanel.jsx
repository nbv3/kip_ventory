import React, { Component } from 'react'
import { Grid, Row, Col, Button, Modal, Table, Form, Glyphicon, Pagination,
         FormGroup, FormControl, ControlLabel, HelpBlock, Panel, InputGroup,
         Label, Well, Badge, ListGroup, ListGroupItem } from 'react-bootstrap'
import { getJSON, ajax } from "jquery"
import { getCookie } from '../../../csrf/DjangoCSRFToken'
import { browserHistory } from 'react-router'
import Select from 'react-select'
import LoanModal from '../../loans/LoanModal'

const ManagerLoanPanel = React.createClass({

  getInitialState() {
    return {
      showModal: false,
      loanToModify: null,
    }
  },

  isAllReturned() {
    for (var i=0; i<this.props.loanGroup.loans.length; i++) {
      var loan = this.props.loanGroup.loans[i]
      if (loan.quantity_loaned > loan.quantity_returned) {
        return false
      }
    }
    return true
  },

  getExpandChevron() {
    return (this.props.expanded === this.props.index) ? (
      <Glyphicon style={{fontSize:"12px"}} glyph="chevron-up" />
    ) : (
      <Glyphicon style={{fontSize:"12px"}} glyph="chevron-down" />
    )
  },

  getRequestStatusSymbol(fs) {
    return (this.isAllReturned()) ? (
      <Glyphicon style={{color: "#5cb85c", fontSize: fs}} glyph="ok-sign" />
    ) : (
      <Glyphicon style={{color: "#f0ad4e", fontSize:"18px"}} glyph="exclamation-sign" />
    )
  },

  getRequestSubtitle() {
    return (this.isAllReturned()) ? (
      "All items in this request have been disbursed or returned to the inventory."
    ) : (
      "One or more items in this request are still on loan."
    )
  },

  getLoanStatusSymbol(loan, fs) {
    return (loan.quantity_returned === loan.quantity_loaned) ? (
      <Glyphicon style={{color: "#5cb85c", fontSize: fs}} glyph="ok-sign" />
    ) : (
      <Glyphicon style={{color: "#f0ad4e", fontSize: fs}} glyph="exclamation-sign" />
    )
  },

  getPanelStyle() {
    return (this.props.index === this.props.expanded) ? (
      {margin:"10px 0px", boxShadow: "0px 0px 5px 2px #485563"}
    ) : (
      {margin:"0px"}
    )
  },

  showModal(loan) {
    this.setState({
      showModal: true,
      loanToModify: loan,
      returnQuantity: 1,
      disburseQuantity: 1
    })
  },

  hideModal(e) {
    this.setState({
      showModal: false,
      loanToModify: null,
      returnQuantity: 1,
      disburseQuantity: 1
    })
  },


  getLoansCard(loans, request) {
    return (loans.length > 0) ? (
      <Table style={{marginBottom: "0px"}}>
        <thead>
          <tr>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-center">Status</th>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-left">Item</th>
            <th style={{width:"50%", borderBottom: "1px solid #596a7b"}} className="text-left">Asset</th>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-center">Loaned</th>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-center">Returned</th>
          </tr>
        </thead>
        <tbody>
          { loans.map( (loan, i) => {
            var modifyIfOutstanding = null
            if (loan.quantity_loaned > loan.quantity_returned) {
              modifyIfOutstanding = (
                <Glyphicon glyph="edit" className="clickable" style={{color: "#5bc0de", fontSize: "12px"}}
                           onClick={this.showModal.bind(this, loan)} />
              )
            }
            return (
              <tr key={loan.id}>
                <td data-th="" className="text-center">
                  { this.getLoanStatusSymbol(loan, "15px") }
                </td>
                <td data-th="Item" className="text-left">
                  <a href={"/app/inventory/" + loan.item + "/"} style={{fontSize: "12px", color: "rgb(223, 105, 26)"}}>
                    { loan.item }
                  </a>
                </td>
                {(loan.asset == null) ? (
                  <td data-th="Asset" className="text-left">

                  </td>
                ) : (
                  <td data-th="Asset" className="text-left">
                    { loan.asset }
                  </td>
                )}
                <td data-th="Loaned" className="text-center">
                  { loan.quantity_loaned }
                </td>
                <td data-th="Returned" className="text-center">
                  { loan.quantity_returned }
                </td>
                <td data-th="" className="text-center">
                  { modifyIfOutstanding }
                </td>
              </tr>
            )
          })}
        </tbody>
      </Table>
    ) : (
      <Well bsSize="small" style={{fontSize: "12px"}} className="text-center">
        This request has no associated loans.
      </Well>
    )
  },

  getDisbursementsCard(disbursements, request) {
    return (disbursements.length > 0) ? (
      <Table style={{marginBottom: "0px"}}>
        <thead>
          <tr>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-center">Status</th>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-left">Item</th>
            <th style={{width:"70%", borderBottom: "1px solid #596a7b"}} className="text-left">Asset</th>
            <th style={{width:"10%", borderBottom: "1px solid #596a7b"}} className="text-center">Quantity</th>
          </tr>
        </thead>
        <tbody>
          { disbursements.map( (disbursement, i) => {
            return (
              <tr key={disbursement.id}>
                <td data-th="Status" className="text-center">
                  <Glyphicon style={{color: "rgb(217, 83, 79)", fontSize: "15px"}} glyph="log-out" />
                </td>
                <td data-th="Item" className="text-left">
                  <a href={"/app/inventory/" + disbursement.item + "/"} style={{fontSize: "12px", color: "rgb(223, 105, 26)"}}>
                    { disbursement.item }
                  </a>
                </td>
                {(disbursement.asset == null) ? (
                  <td data-th="Asset" className="text-left">

                  </td>
                ) : (
                  <td data-th="Asset" className="text-left">
                    { disbursement.asset }
                  </td>
                )}
                <td data-th="Quantity" className="text-center">
                  { disbursement.quantity }
                </td>
              </tr>
            )
          })}
        </tbody>
      </Table>
    ) : (
      <Well bsSize="small" style={{fontSize: "12px"}} className="text-center">
        This request has no associated disbursements.
      </Well>
    )
  },

  render() {
    var request = this.props.loanGroup.request
    var loans = this.props.loanGroup.loans
    var disbursements = this.props.loanGroup.disbursements
    return (
      <ListGroupItem style={{borderTop: "2px solid #485563", borderBottom: "2px solid #485563"}}>

        <Row className="clickable" onClick={this.props.toggleExpanded} style={{display: "flex"}}>
          <Col xs={1} style={{display: "flex", flexDirection:"column", justifyContent: "center", textAlign: "center"}}>
            { this.getRequestStatusSymbol("18px") }
          </Col>
          <Col xs={3} style={{paddingLeft: "0px"}}>
            <div style={{padding: "5px 0px", fontSize:"15px"}}>
              <span style={{fontSize:"15px"}}>Request #{request.id}</span>
            </div>
            <a style={{fontSize:"12px"}} href={"/app/requests/" + request.id + "/"} onClick={e => {e.stopPropagation()}}>Click to view request</a>
            <p style={{fontSize: "12px"}}>Requested by: <span style={{color:"#df691a"}}>{ request.requester }</span></p>
          </Col>
          <Col xs={7} style={{display: "flex", flexDirection:"column", justifyContent: "center"}}>
            <span style={{fontSize:"12px", float: "right"}}>
              { this.getRequestSubtitle() }
            </span>
          </Col>
          <Col xs={1} style={{display: "flex", flexDirection:"column", justifyContent: "center", textAlign: "center"}}>
            { this.getExpandChevron() }
          </Col>
        </Row>

        <Row>
          <Col md={6} xs={12} >
            <Panel style={ this.getPanelStyle() } collapsible defaultExpanded={false} expanded={this.props.expanded === this.props.index}>
              <span style={{fontSize:"15px", margin: "10.5px 0px"}}>Loans</span>
              <hr style={{marginTop: "0px"}}/>
              { this.getLoansCard(loans, request) }
            </Panel>
          </Col>

          <Col md={6} xs={12} >
            <Panel style={ this.getPanelStyle() } collapsible defaultExpanded={false} expanded={this.props.expanded === this.props.index}>
              <span style={{fontSize:"15px", margin: "10.5px 0px"}}>Disbursements</span>
              <hr style={{marginTop: "0px"}}/>
              { this.getDisbursementsCard(disbursements, request) }
            </Panel>
          </Col>
        </Row>

        <LoanModal loan={this.state.loanToModify}
                   request={request}
                   show={this.state.showModal}
                   onHide={this.hideModal}
                   refresh={this.props.getLoanGroups} />

      </ListGroupItem>
    );
  }
});

export default ManagerLoanPanel
