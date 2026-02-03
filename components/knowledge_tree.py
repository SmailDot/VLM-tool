
import streamlit as st
import streamlit.components.v1 as components
import json

def render_d3_tree(tree_data, height=600):
    """
    Render an interactive D3.js Collapsible Tree.
    """
    
    # Pass data as JSON string
    tree_json = json.dumps(tree_data)
    
    # Use {{ }} for Python f-string escape
    # Use ${ } for JavaScript template literal (which needs to be output as ${ } in final HTML)
    # So in f-string: ${{var}} becomes ${var} in JS
    
    html_code = f"""
    <!DOCTYPE html>
    <meta charset="utf-8">
    <style>
    
    .node circle {{
      fill: #fff;
      stroke: #555;
      stroke-width: 3px;
      cursor: pointer;
      transition: all 0.3s ease;
    }}
    
    .node circle:hover {{
      fill: #ff9800; /* Orange highlight */
      transform: scale(1.2);
    }}

    .node text {{
      font: 14px sans-serif;
      fill: #333;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }}

    .link {{
      fill: none;
      stroke: #ccc;
      stroke-width: 2px;
      opacity: 0.7;
    }}
    
    .tooltip {{
        position: absolute;
        text-align: center;
        padding: 8px;
        font: 12px sans-serif;
        background: rgba(0, 0, 0, 0.8);
        color: white;
        border-radius: 4px;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.2s;
    }}

    body {{
        background-color: transparent; /* Streamlit friendly */
        overflow: hidden;
    }}
    
    </style>
    <body>
    <div id="tree-container"></div>
    
    <!-- Load D3.js from CDN -->
    <script src="https://d3js.org/d3.v7.min.js"></script>
    
    <script>
    
    var treeData = {tree_json};

    var margin = {{top: 20, right: 90, bottom: 30, left: 90}},
        width = 960 - margin.left - margin.right,
        height = {height} - margin.top - margin.bottom;

    var svg = d3.select("#tree-container").append("svg")
        .attr("width", "100%")
        .attr("height", height + margin.top + margin.bottom)
        .call(d3.zoom().on("zoom", function (event) {{
            svg.attr("transform", event.transform)
        }}))
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    var i = 0,
        duration = 750,
        root;

    var treemap = d3.tree().size([height, width]);

    root = d3.hierarchy(treeData, function(d) {{ return d.children; }});
    root.x0 = height / 2;
    root.y0 = 0;

    // Collapse after the second level
    // root.children.forEach(collapse);

    update(root);

    function collapse(d) {{
      if(d.children) {{
        d._children = d.children
        d._children.forEach(collapse)
        d.children = null
      }}
    }}

    function update(source) {{

      var treeData = treemap(root);

      var nodes = treeData.descendants(),
          links = treeData.descendants().slice(1);

      nodes.forEach(function(d){{ d.y = d.depth * 180}});

      var node = svg.selectAll('g.node')
          .data(nodes, function(d) {{return d.id || (d.id = ++i); }});

      var nodeEnter = node.enter().append('g')
          .attr('class', 'node')
          .attr("transform", function(d) {{
            return "translate(" + source.y0 + "," + source.x0 + ")";
        }})
        .on('click', click);

      nodeEnter.append('circle')
          .attr('class', 'node')
          .attr('r', 1e-6)
          .style("fill", function(d) {{
              return d._children ? "#ff9800" : "#fff";
          }});

      nodeEnter.append('text')
          .attr("dy", ".35em")
          .attr("x", function(d) {{
              return d.children || d._children ? -13 : 13;
          }})
          .attr("text-anchor", function(d) {{
              return d.children || d._children ? "end" : "start";
          }})
          .text(function(d) {{ return d.data.name; }});

      var nodeUpdate = nodeEnter.merge(node);

      nodeUpdate.transition()
        .duration(duration)
        .attr("transform", function(d) {{ 
            return "translate(" + d.y + "," + d.x + ")";
         }});

      nodeUpdate.select('circle.node')
        .attr('r', 10)
        .style("fill", function(d) {{
            return d._children ? "#ff9800" : "#fff"; // Orange if collapsed
        }})
        .attr('cursor', 'pointer');


      var nodeExit = node.exit().transition()
          .duration(duration)
          .attr("transform", function(d) {{
              return "translate(" + source.y + "," + source.x + ")";
          }})
          .remove();

      nodeExit.select('circle')
        .attr('r', 1e-6);

      nodeExit.select('text')
        .style('fill-opacity', 1e-6);

      var link = svg.selectAll('path.link')
          .data(links, function(d) {{ return d.id; }});

      var linkEnter = link.enter().insert('path', "g")
          .attr("class", "link")
          .attr('d', function(d){{
            var o = {{x: source.x0, y: source.y0}}
            return diagonal(o, o)
          }});

      var linkUpdate = linkEnter.merge(link);

      linkUpdate.transition()
          .duration(duration)
          .attr('d', function(d){{ return diagonal(d, d.parent) }});

      var linkExit = link.exit().transition()
          .duration(duration)
          .attr('d', function(d) {{
            var o = {{x: source.x, y: source.y}}
            return diagonal(o, o)
          }})
          .remove();

      nodes.forEach(function(d){{
        d.x0 = d.x;
        d.y0 = d.y;
      }});

      function diagonal(s, d) {{
        // Properly escaped f-string for JS template literal
        var path = `M ${{s.y}} ${{s.x}}
                C ${{ (s.y + d.y) / 2 }} ${{s.x}},
                  ${{ (s.y + d.y) / 2 }} ${{d.x}},
                  ${{d.y}} ${{d.x}}`

        return path
      }}

      // Toggle children on click.
      function click(event, d) {{
        if (d.children) {{
            d._children = d.children;
            d.children = null;
          }} else {{
            d.children = d._children;
            d._children = null;
          }}
        update(d);
      }}
    }}

    </script>
    </body>
    """
    
    components.html(html_code, height=height, scrolling=True)
