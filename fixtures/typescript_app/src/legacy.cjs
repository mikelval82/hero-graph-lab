const gateway = require("./gateway");
const telegram = require("telegram");

function dispatch(message) {
  return gateway.format(message);
}

module.exports = { dispatch, telegram };
