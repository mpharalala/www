$(document).ready(function(){

    $("#email").keyup(function(){
         $("#login_btn").attr("onclick","user_exists()");
         $(".form_toggle").addClass("d-none");
         $("#passw").val("")
         $("#base_station_name").val("")
         $("#mac_address").val("")
    });


    $(".table").DataTable({
        "ordering":false,
        "searching":true,
        "paging":true
    });


    $.validator.setDefaults({
        errorClass: 'text-danger',
        highlight: function(element){
            $(element).addClass('is-invalid')
        },
        unhighlight: function(element){
            $(element).addClass("is-valid")
            $(element).removeClass("is-invalid")
        }
    });

    $.validator.addMethod(
        "strongPassword",
        function(value, element){
            return value.length >=1;
        },
        "Your password must at least 1 characters long"
    );

     $.validator.addMethod(
        "mac_address_regex",
        function(value, element) {
            return /^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])\w{6,}$/.test(value);
    }, "Please enter a Valid Mac Address");

    $.validator.addMethod(
        "customEmail",
        function(value, element){
            return /^([a-zA-Z0-9_.\-+])+\@(([a-zA-Z0-9-])+.)\.+([a-zA-Z0-9]{2,4})+$/.test(value);;
        },
        "Please type a valid Email"
    );

    $("#login_form").validate({
        rules:{
            email:{
                required : true,
                customEmail: true
            },
            passw:{
                required : true,
                strongPassword : true
            },
            mac_address:{
                mac_address_regex : true
            }
        },
    });

})

function dontSubmit(){
    return false;
}

function user_exists(){
    if($("#login_form").validate().element("#email")){
        $("#login_btn").addClass("disabled");
        $.get("/user_exists",{email:$("#email").val()})
        .done(
            function(data){
                if(data['code']==100){
                    $(".form_toggle").removeClass("d-none")
                    $("#login_btn").attr("onclick","register()");
                }else{
                    if(data['code']=402){
                        growl(data["message"], "danger")
                        $(".form_toggle").addClass("d-none")
                    }else{
                        growl("TInternal Server Error. Please try again or contact admin","danger")
                        $(".form_toggle").addClass("d-none")
                    }
                }
            }
        )
        .always(
            function(){
                $("#login_btn").removeClass("disabled");
                $("#login_btn").html("Log in");
            }
        )
        .fail(function()
            {
                growl("Internal Server Error. Please try again or contact admin", "danger")
                $(".form_toggle").addClass("d-none")
                $("#login_btn").attr("onclick","user_exists()");
            }
        )
    }
    return false;
}


function growl(message, type){
    $.bootstrapGrowl(message, {
                      ele: 'body', // which element to append to
                      type: type, // (null, 'info', 'danger', 'success')
                      offset: {from: 'top', amount: 20}, // 'top', or 'bottom'
                      align: 'center', // ('left', 'right', or 'center')
                      width: 'auto', // (integer, or 'auto')
                      delay: 10000, // Time while the message will be displayed. It's not equivalent to the *demo* timeOut!
                      allow_dismiss: true, // If true then will display a cross to close the popup.
                      stackup_spacing: 10 // spacing between consecutively stacked growls.
    });
}


function register_api(){
    var win = window.open('http://192.168.0.59:5000/register', '_blank');
    if (win) {
        //Browser has allowed it to be opened
        win.focus();
    } else {
        //Browser has blocked it
        growl("Please allow popups for this website to access register site", "info")
    }
}



function register(){
    email = $("#email").val();
    password = $("#passw").val();
    address = $("#mac_address").val();
    name = $("#base_station_name").val();
    if ($("#login_form").valid()){
        $("#login_btn").html("Loading......");
        $("#login_btn").addClass("disabled");
        $.post("/register_address", {email:email,password:password,address:address,name:name})
        .done(
            function(data){
            if((data['code']==200)||(data['code']==500)||(data['code']==401)||(data['code']==404)){
                if(data['code']==200){
                    growl(data["message"], "success")
                }else{
                    growl(data["message"], "danger")
                }
            }else{
                growl("Internal Server Error. Please try again or contact admin", "danger")
                $(".form_toggle").addClass("d-none")
                $("#login_btn").attr("onclick","user_exists()");
            }
        })
        .always(
            function(){
                $("#login_btn").html("Log In");
                $("#login_btn").removeClass("disabled");
            })
        .fail(function(){
            growl("Internal Server Error. Please try again or contact admin", "danger")
            $(".form_toggle").addClass("d-none")
            $("#login_btn").attr("onclick","user_exists()");
        })
    }
    return false;
}