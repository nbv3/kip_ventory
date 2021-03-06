import React from 'react'
import { Grid, Row, Col } from 'react-bootstrap'
import ReactPaginate from 'react-paginate'

function Paginator(props) {

  return (
           <ReactPaginate previousLabel={"<"}
                   nextLabel={">"}
                   breakLabel={<a href="">...</a>}
                   breakClassName={"break-me"}
                   pageCount={props.pageCount}
                   marginPagesDisplayed={2}
                   pageRangeDisplayed={5}
                   onPageChange={props.onPageChange}
                   forcePage={props.forcePage}
                   containerClassName={"pagination"}
                   subContainerClassName={"pages pagination"}
                   activeClassName={"active"} />
  )
}

export default Paginator
