/*---------------------------------------------------------
  * By Dainier Escalona Barles
 * 2022-05-11
 *---------------------------------------------------------*/
(function() {

    $(document).ready(function () {
        console.log('document ready');

		if ($(".kushki-form")[0]){
            console.log('public_key', $("#public_key").text());
            console.log('kushki_kformid', $("#kushki_kformid").text());
            console.log('test_environment', $("#test_environment").text());
            console.log('total', $("#id_total").text());

			var public_key = $("#public_key").text();
			var total = parseFloat($("#id_total").text());
			var test_environment = $("#test_environment").text();
			console.log(total);

			var kushki = new KushkiCheckout({
			    kformId: $("#kushki_kformid").text(),
			    form: "kushki-form",
			    publicMerchantId: public_key, // Reemplaza esto por tu credencial pública
			    inTestEnvironment: test_environment,
			    amount: {
			     subtotalIva: 0,
			     iva: 0,
			     subtotalIva0: total,
			    }
		    });

		}


    });


})();

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax: