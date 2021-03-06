$(document).ready(function(){

    $('#register_btn').attr("href","http://localhost:5003/register")


    //Change first letter of input with class firstLetterUpperCase
    $('.firstLetterUpperCase').keyup(function(){
    if($(this).val().length>0 && $(this).val().length<5){
        $(this).val($(this).val().charAt(0).toUpperCase()+$(this).val().substr(1));
        }
    });


    $("#email").keyup(function(){
         $("#login_btn").attr("onclick","user_exists()");
         $("#login_btn").text("Verify Email Address");
         $(".form_toggle").addClass("d-none");
         $("#passw").val("")
         $("#base_station_name").val("")
    });


    $(".lowercase").keyup(function(){
         $(this).val($(this).val().toLowerCase())
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
                required : true
            },
            passw:{
                required : true,
                strongPassword : true
            },
            mac_address:{
//                mac_address_regex : true
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
                    if ($("#login_btn").hasClass("login")){
                        $("#login_btn").attr("onclick","log_in()");
                        $("#login_btn").html("Log In");
                    }else{
                        $("#login_btn").attr("onclick","register()");
                        $("#login_btn").html("Register Base Station");
                    }
                }else{
                    if(data['code']=402){
                        growl(data["message"], "danger")
                        $(".form_toggle").addClass("d-none")
                    }else{
                        growl("TInternal Server Error. Please try again or contact admin","danger")
                        $(".form_toggle").addClass("d-none")
                    }
                }
                $("#login_btn").removeClass("disabled");
            }
        )
        .fail(
            function(){
                growl("Internal Server Error. Please try again or contact admin", "danger")
                $(".form_toggle").addClass("d-none")
                $("#login_btn").attr("onclick","user_exists()");
                $("#login_btn").removeClass("disabled");
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

function register(){
    email = $("#email").val();
    password = $("#passw").val();
    address = $("#mac_address").val();
    name = $("#base_station_name").val();
    rate = $("#internet_rate").val()
    if ($("#login_form").valid()){
        $("#login_btn").html("Loading......");
        $("#login_btn").addClass("disabled");
        $.post("/register_base_station", {email:email,password:password,address:address,name:name,rate:rate})
        .done(
            function(data){
            if((data['code']==200)||(data['code']==500)||(data['code']==401)||(data['code']==404)){
                if(data['code']==200){
                    location.replace("/dashboard/nodes");
                }else{
                    growl(data["message"], "danger")
                     $("#login_btn").removeClass("disabled");
                }
            }else{
                growl("Internal Server Error. Please try again or contact admin", "danger")
                $(".form_toggle").addClass("d-none")
                $("#login_btn").attr("onclick","user_exists()");
                 $("#login_btn").removeClass("disabled");
            }
        })
        .always(
            function(){
                $("#login_btn").html("Register Station");
            })
        .fail(function(){
            growl("Internal Server Error. Please try again or contact admin", "danger")
            $(".form_toggle").addClass("d-none")
            $("#login_btn").attr("onclick","user_exists()");
             $("#login_btn").removeClass("disabled");
        })
    }
    return false;
}

function log_in(){
    email = $("#email").val();
    password = $("#passw").val();
    if ($("#login_form").valid()){
        $("#login_btn").html("Loading......");
        $("#login_btn").addClass("disabled");
        $.post("/login", {email:email,password:password})
        .done(
            function(data){
            if((data['code']==100)||(data['code']==401)||(data['code']==403)){
                if(data['code']==100){
                    location.href = "/dashboard/nodes";
                }else{
                    if(data['code']==403){
                        location.href = "/";
                    }else{
                        growl(data["message"], "danger")
                         $("#login_btn").removeClass("disabled");
                    }
                }
            }else{
                growl("Internal Server Error. Please try again or contact admin", "danger")
                $(".form_toggle").addClass("d-none")
                $("#login_btn").attr("onclick","user_exists()");
                 $("#login_btn").removeClass("disabled");
            }
        })
        .always(
            function(){
                $("#login_btn").html("Log In");
            })
        .fail(function(){
            growl("Internal Server Error. Please try again or contact admin", "danger")
            $(".form_toggle").addClass("d-none")
            $("#login_btn").attr("onclick","user_exists()");
            $("#login_btn").removeClass("disabled");
        })
    }
    return false;
}

function create_table(table_name){

    var columns = []
    if (table_name=="nodes"){
        columns = [{"data": "Name"}, {"data": "Disk"}, {"data": "Memory"}, {"data": "Disk Pressure"},
                              {"data": "Age"}, {"data": "Activity"}, {"data": "Status"}]
    }else if (table_name=="pods"){
        columns = [{data: "Name",},{data: "Container Image"},{data: "Container Name"},
            {data: "Container Port"},{data: "Protocol"},{data: "Age"},{data: "Activity"},{data: "Status"}]
    }else if (table_name=="services"){
        columns = [{data: "Name",},{data: "Cluster IP"},{data: "Node Port"},{data: "Port"},
                    {data: "Protocol"},{data: "Target Port" },{data: "Type"},{data: "Age"}]
    }else if (table_name="deployments"){
        columns = [{data: "Name",},{data: "Last Update Time"},{data: "Reason"},
                    {data: "Type"},{data: "Replicas"},{data: "Status"},{data: "Age"}]
    }
    $("#"+table_name+"_table").DataTable( {
        "responsive": true,
        "autoWidth": false,
        "ajax": function(data, callback, settings){
            $.ajax({
                url: "/"+table_name,
                data: data,
                success:function(data){
                    if (data['code'] == "200"){
                        callback(data[table_name])
                        refresh_table(table_name)
                    }else{
                        if (data['code'] == "202"){
                            growl(data['message'],"info")
                            var data = {"data":[]}
                            callback(data)
                            re_initialise_table(table_name)
                        }
                    }
                },
                error:function(data){
                    growl("Internal Server Error. Try to refresh page or contact support","danger")
                }
            })
        },
        'columns': columns
    });
}

function re_initialise_table(name){
    setTimeout(function(){
        $("#"+name+"_table").DataTable().destroy();
        create_table(name)
     }, 10000);
}

function refresh_table(name){
    setTimeout( function () {
        $("#"+name+"_table").DataTable().ajax.reload(null, false);
    }, 10000 );
}