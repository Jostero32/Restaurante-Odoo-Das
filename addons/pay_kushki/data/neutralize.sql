-- disable kushki payment provider
UPDATE payment_provider
   SET kushki_publicmerchantmd = NULL,
       kushki_privatemerchantmd = NULL,
       kushki_kformid = NULL,
       kushki_intestenvironment = NULL,
       kushki_url = NULL,
       kushki_sitedomain = NULL,
       kushki_url_otp = NULL;
