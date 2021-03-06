import React, { Component } from 'react'
import { Form, Grid, Row, Button, Col, ListGroup, ListGroupItem, FormGroup, FormControl, ControlLabel, Alert, Pagination } from 'react-bootstrap'
import $ from "jquery"
import { getJSON, ajax } from 'jquery'
import { getCookie } from '../../../csrf/DjangoCSRFToken'

const TAGS_PER_PAGE = 3

class TagsContainer extends Component{
  constructor(props) {
    super(props);
    this.state = {
      tags: [],
      name: "",
      showCreatedSuccess: false,
      createdMessage: "",
      showErrorMessage: false,
      errorMessage: "",
      page: 1,
      pageCount: 1,
    }

    //this.getAllTags = this.getAllTags.bind(this);
    this.getTags = this.getTags.bind(this);
    this.createTag = this.createTag.bind(this);
    this.deleteTag = this.deleteTag.bind(this);
    this.updateTagList = this.updateTagList.bind(this);
    this.getTagList = this.getTagList.bind(this);
    this.handlePageSelect = this.handlePageSelect.bind(this);

    this.getTags();
  }

/*
  getAllTags(){
      var url = "/api/tags/?all=true"
      var _this = this
      getJSON(url, function(data) {
        _this.setState({
          tags: data,
        });
      })
  }
  */

  getTags() {
    var url = "/api/tags/"
    var params = {
      page: this.state.page,
      itemsPerPage: TAGS_PER_PAGE,
    }
    var _this = this
    getJSON(url, params, function(data) {
      _this.setState({
        tags: data.results,
        pageCount: data.num_pages,
      });
    })
  }

  handleChange(name, e) {
    var change = {};
    change[name] = e.target.value;
    this.setState(change);
  }

  createTag(event){
    event.preventDefault();
    var _this = this

    if(this.state.name == ""){
      //TODO show error here
      console.log("Can't create blank tag")
    } else{
      $.ajax({
        url:"/api/tags/",
        type: "POST",
        beforeSend: function(request) {
          request.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        },
        data: {
          name: this.state.name,
        },
        traditional: true,
        success:function(response){
          var name = response.name
          _this.getTags();
          _this.setState({
            name: "",
            showCreatedSuccess: true,
            createdMessage: "Tag '" + name + "' successfully created.",
            showErrorMessage: false,
            errorMessage: ""
          })
        },
        complete:function(){

        },
        error:function (xhr, textStatus, thrownError){
          var response = xhr.responseJSON
          console.log(response)
          _this.setState({
            showCreatedSuccess: false,
            createdMessage: "",
            showErrorMessage: true,
            errorMessage: "A " + response.name[0]
          })
        }
      });
    }
  }

  deleteTag(event, tag){
    event.preventDefault();

    var _this = this
    $.ajax({
      url:"/api/tags/"+tag.name+"/",
      type: "DELETE",
      beforeSend: function(request) {
        request.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
      },
      success:function(response){
        var page = _this.state.page;
        if(_this.state.tags.length<=1) {
          page = page == 1 ? page : page-1;
        }
        _this.setState({
          page: page,
          showCreatedSuccess: false,
          showErrorMessage: false,
          errorMessage: "",
          createdMessage: ""
        }, _this.getTags)
  
      },
      complete:function(){
          },
      error:function (xhr, textStatus, thrownError){
        _this.setState({
          showErrorMessage: false,
          errorMessage: "Error deleting tag.",
        });
      }
    });
  }

  updateTagList(tags){
    this.setState({tags: tags});
  }

  getTagList(){
    var html = [];

    html.push(this.state.tags.map( (tag, i) => {
      return (<ListGroupItem><Row><Col xs={10}>{tag.name} </Col><Col xs={2}><Button bsStyle="danger" onClick={e => {this.deleteTag(e, tag)}}>Delete</Button></Col></Row></ListGroupItem>);
    }));

    return html;
  }


  showSuccessMessage() {
    var ret = this.state.showCreatedSuccess ? (
      <Row>
        <Col sm={12}>
          <Alert bsSize="small" bsStyle="success">{this.state.createdMessage}</Alert>
        </Col>
      </Row>) : (null)
    return ret
  }

  showErrorMessage() {
    return this.state.showErrorMessage ? (
      <Row>
        <Col sm={12}>
          <Alert bsStyle="danger" bsSize="small">{this.state.errorMessage}</Alert>
        </Col>
      </Row>
    ) : null
  }

  handlePageSelect(activeKey) {
    this.setState({page: activeKey}, () => {
      this.getTags();
    })
  }

  render(){
    var tagList = this.getTagList();
    var finalList = (<ListGroup>{tagList}</ListGroup>);
    return (
        <Grid fluid>
          <Row>

            <Col sm={12}>
              <h3>Manage Tags</h3>
              <hr />
              <p>
                Create and delete tags in the system.
              </p>
              <br />
            </Col>
          </Row>
          <Row>
            <Form horizontal onSubmit={e => e.preventDefault()}>
              <FormGroup controlId="newTagForm">
                <Col componentClass={ControlLabel} sm={2}>
                  New Tag:
                </Col>
                <Col sm={6}>
                  <FormControl
                    type="text"
                    name="name"
                    value={this.state.name ? this.state.name : ""}
                    placeholder={this.state.name}
                    onChange={this.handleChange.bind(this, 'name')}
                  ></FormControl>
                </Col>
                <Col sm={3}>
                  <Button onClick={e =>{this.createTag(e)}}>Create Tag</Button>
                </Col>
              </FormGroup>
            </Form>
          </Row>

          { this.showErrorMessage() }
          { this.showSuccessMessage() }

          <Row>
            <Col sm={12} style={{maxHeight: '500px', overflow: 'auto'}}>
              {finalList}
            </Col>
          </Row>

          <Row>
            <Col md={12}>
              <Pagination next prev maxButtons={10} boundaryLinks ellipsis style={{float:"right", margin: "0px"}} bsSize="small" items={this.state.pageCount} activePage={this.state.page} onSelect={this.handlePageSelect} />
            </Col>
          </Row>
        </Grid>
    );
  }



}


export default TagsContainer
