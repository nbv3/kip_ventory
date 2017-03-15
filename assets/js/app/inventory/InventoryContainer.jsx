import React, { Component } from 'react'
import { Grid, Row, Col, Table, Image, Button, Panel, Label, Glyphicon } from 'react-bootstrap'
import InventoryItem from './InventoryItem'
import InventoryGridHeader from './InventoryGridHeader'
import Paginator from '../Paginator'
import { getJSON } from 'jquery'
import { browserHistory } from 'react-router';

const ITEMS_PER_PAGE = 5;

class InventoryContainer extends Component {
  constructor(props) {
    super(props);

    this.state = {
      items:[],
      tagsSelected: [],
      excludeTagsSelected: [],
      searchText: "",
      page: 1,
      pageCount: 0,
    };

    this.getItems = this.getItems.bind(this);
    this.getAllItems = this.getAllItems.bind(this);
    this.filterItems = this.filterItems.bind(this);

    this.handleSearch = this.handleSearch.bind(this);
    this.handleTagSelection = this.handleTagSelection.bind(this);
    this.handleExcludeTagSelection = this.handleExcludeTagSelection.bind(this);
    this.handlePageClick = this.handlePageClick.bind(this);

    this.getAllItems(); //maybe move to componentDidMount()
  }

  getItems(params) {
    var url = "/api/items/";
    var thisobj = this;
    getJSON(url, params, function(data) {
      thisobj.setState({
        items: data.results,
        pageCount: Math.ceil(data.num_pages),
      });
    });
  }

  getAllItems() {
    var params = {
      page: 1,
      itemsPerPage: ITEMS_PER_PAGE
    }

    this.getItems(params);
  }

  filterItems() {
    var params = {
      search: this.state.searchText,
      tags: this.state.tagsSelected,
      excludeTags: this.state.excludeTagsSelected,
      page: this.state.page,
      itemsPerPage: ITEMS_PER_PAGE
    }

    this.getItems(params);
  }

  handleSearch(text) {
    this.setState({searchText: text, page: 1}, () => {
      this.filterItems();
    });
  }

  handleTagSelection(tagsSelected) {
    this.setState({tagsSelected: tagsSelected, page: 1}, () => {
      this.filterItems();
    });
  }

  handleExcludeTagSelection(excludeTagsSelected) {
    this.setState({excludeTagsSelected: excludeTagsSelected, page: 1}, () => {
      this.filterItems();
    });
  }

  handlePageClick(data) {
    let selected = data.selected;
    let offset = Math.ceil(selected * ITEMS_PER_PAGE);
    let page = data.selected + 1;

    this.setState({page: page}, () => {
      this.filterItems();
    });
  }

  handleChangeQuantity(index, quantity) {
    this.setState(function(prevState, props) {
      prevState.items[index].quantity = parseInt(prevState.items[index].quantity) + parseInt(quantity);
      return {
        items: prevState.items
      };
    });
  }

  render() {
    return (
      <Grid>
        <Row>
          <Col sm={12} smOffset={0}>
            <Row>
              <Col sm={12}>
                <h3>Inventory</h3>
                <hr />
              </Col>
            </Row>

            <Row>
              <Col sm={12}>
                <InventoryGridHeader searchHandler={this.handleSearch} tagHandler={this.handleTagSelection} tagsSelected={this.state.tagsSelected} excludeTagHandler={this.handleExcludeTagSelection} excludeTagsSelected={this.state.excludeTagsSelected}/>
              </Col>
            </Row>

            <hr />

            <Row>
              <Col sm={12}>
                <Table condensed>
                  <thead>
                    <tr>
                      <th style={{width:"25%"}} className="text-left">Item Information</th>
                      <th style={{width:"5%" }} className="spacer"></th>
                      <th style={{width:"10%"}} className="text-center">Model No.</th>
                      <th style={{width:"10%"}} className="text-center">Available</th>
                      <th style={{width:"5%" }} className="spacer"></th>
                      <th style={{width:"10%"}} className="text-left">Tags</th>
                      <th style={{width:"10%"}} className="text-center"></th>
                      <th style={{width:"8%" }} className="text-center">Quantity</th>
                      <th style={{width:"12%"}} className="text-center"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {this.state.items.map( (item, i) => {
                      return (<InventoryItem key={item.name} item={item} />)
                    })}
                  </tbody>
                </Table>
              </Col>
            </Row>
            <Row>
              <Col sm={4} smOffset={4}>
                <Paginator pageCount={this.state.pageCount} onPageChange={this.handlePageClick} forcePage={this.state.page - 1}/>
              </Col>
            </Row>
          </Col>
        </Row>
      </Grid>
    )
  }
}

export default InventoryContainer
