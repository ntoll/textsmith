$(document).ready(function(){
    // Create a connection to the server and call it "websocket".
    var protocol = "wss://";
    if(location.protocol === "http:") {
        protocol = "ws://";
    }
    var websocket = new WebSocket(protocol + document.domain + ':' + location.port + '/ws');

    // Define what to do when our websocket gets a message from the server.
    websocket.onmessage = function(e) {
        // Just call onMessageAdded with the raw data from the server.
        onMessageAdded(e.data);
    }

    // Define what to do when the submit button is clicked.
    $('#send').click(function(){
        // Just call sendMessage.
        sendMessage();
    });

    // Define what to do when the textarea has focus and the user types
    // CTRL-ENTER.
    $("#input").keydown(function(event) {
        // Check the keydown event is BOTH CTRL key and ENTER (keycode 13).
        if (event.ctrlKey && event.keyCode === 13) {
            // Just call sendMessage.
            sendMessage();
        }
    })

    // Handle the sending of whatever is in the textarea as a message to the
    // server.
    function sendMessage(){
        // Extract the raw message.
        const message = $("#input").val();
        // Reset the textarea to an empty string.
        $("#input").val("");
        // Send the message to the server.
        websocket.send(message);
        // Ensure the textarea retains focus so users can simply start typing.
        $("#input").focus();
    }

    // Define what to do when the client needs to append data to the output.
    function onMessageAdded(data) {
        // Just append the incoming message to the output section tag.
        $(".output").append(data);
        // Ensure all links outside of this site open in a new browser tab.
        $(document.links).filter(function() {
            return true;
        }).attr('target', '_blank');
        // Scroll to the bottom of the page.
        var element = document.getElementById("send");
        element.scrollIntoView({block: "end"});
    }
});
