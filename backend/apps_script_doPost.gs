function getOrCreateSheet_(name, headers) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    var headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange.setBackground('#1f3d2b'); // forest green
    headerRange.setFontColor('#ffffff');
    headerRange.setFontWeight('bold');
    sheet.setFrozenRows(1);

    var phoneCol = headers.indexOf('Phone') + 1;
    if (phoneCol === 0) phoneCol = headers.indexOf('WhatsApp') + 1;
    if (phoneCol > 0) {
      sheet.getRange(1, phoneCol, sheet.getMaxRows()).setNumberFormat('@');
    }
  }
  return sheet;
}

function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var type = (data.type || '').toLowerCase();

  if (type.indexOf('sample') !== -1) {
    appendSampleRow_(data);
  } else {
    // default: anything else (e.g. "Quote Request") goes to Quotes
    appendQuoteRow_(data);
  }

  return ContentService.createTextOutput(JSON.stringify({ status: 'ok' }))
    .setMimeType(ContentService.MimeType.JSON);
}

function appendQuoteRow_(data) {
  var headers = [
    'S.No', 'Timestamp', 'Name', 'Company', 'Email', 'Phone',
    'Country', 'Buyer Type', 'Product', 'Quantity', 'Incoterm', 'Message'
  ];
  var sheet = getOrCreateSheet_('Quotes', headers);
  var serialNo = sheet.getLastRow(); // header row counts as 0th entry
  var row = [
    serialNo, data.timestamp || '', data.name || '', data.company || '',
    data.email || '', "'" + (data.phone || ''), data.country || '',
    data.buyer_type || '', data.product || '', data.quantity || '',
    data.incoterm || '', data.message || ''
  ];
  sheet.appendRow(row);
}

function appendSampleRow_(data) {
  var headers = [
    'S.No', 'Timestamp', 'Name', 'Company', 'Email', 'WhatsApp',
    'Product', 'Address', 'Purpose'
  ];
  var sheet = getOrCreateSheet_('Samples', headers);
  var serialNo = sheet.getLastRow();
  var row = [
    serialNo, data.timestamp || '', data.name || '', data.company || '',
    data.email || '', "'" + (data.phone || ''), data.product || '',
    data.address || '', data.purpose || ''
  ];
  sheet.appendRow(row);
}
