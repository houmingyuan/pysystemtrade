// pysystemtrade dashboard front end.
//
// Each tab is refreshed from the Flask JSON endpoints. Auto refresh runs every
// window.DASHBOARD_REFRESH_MS milliseconds (injected by the template from
// private_control_config.yaml: dashboard_refresh_seconds); 0 disables it.

var DASHBOARD_REFRESH_MS = (typeof window.DASHBOARD_REFRESH_MS === "number")
  ? window.DASHBOARD_REFRESH_MS
  : 60000;

// --- helpers ---------------------------------------------------------------

function clear_rows(selector) {
  $(selector + " tbody").empty();
}

function set_traffic_light(selector, colour) {
  $(selector).removeClass("red orange green").addClass(colour);
}

function mark_updated() {
  $("#last_updated").text("Last updated " + new Date().toLocaleTimeString());
}

function show_dashboard_message(message) {
  $("#dashboard_message").text(message).removeClass("hidden");
}

function clear_dashboard_message() {
  $("#dashboard_message").addClass("hidden").text("");
}

function display_value(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "number" && isNaN(value)) {
    return "";
  }
  return value;
}

function restore_loading_state(tab_selector) {
  $(tab_selector + " > div.loading").hide();
  $(tab_selector + " > table").show();
}

// --- capital ---------------------------------------------------------------

function update_capital() {
  $.ajax({
    type: "GET",
    url: "/capital",
    success: function(data) {
      $('#capital-tl').html('$' + data['now'].toLocaleString());
      if (data['now'] >= data['yesterday']) {
        set_traffic_light('#capital-tl', 'green');
      } else {
        set_traffic_light('#capital-tl', 'red');
      }
    }
  });
}

// --- costs -----------------------------------------------------------------

function update_costs() {
  $("#costs > div.loading").show();
  $("#costs > table").hide();
  $.ajax({
    type: "GET",
    url: "/costs",
    success: function(data) {
      clear_rows("#costs_table");
      clear_rows("#costs_detail_table");
      $.each(data["table_of_SR_costs"], function(instrument, cost) {
        $("#costs_table tbody").append(
          `<tr><td>${instrument}</td><td>${cost["SR_cost"]}</td></tr>`
        );
      });
      $.each(data["slippage"], function(instrument, vals) {
        $("#costs_detail_table tbody").append(
          `<tr><td>${instrument}</td>
          <td>${vals["% Difference"]}</td>
          <td>${vals["Configured"]}</td>
          <td>${vals["bid_ask_sampled"]}</td>
          <td>${vals["bid_ask_trades"]}</td>
          <td>${vals["estimate"]}</td>
          <td>${vals["total_trades"]}</td>
          <td>${vals["weight_config"]}</td>
          <td>${vals["weight_samples"]}</td>
          <td>${vals["weight_trades"]}</td>
          </tr>`
        );
      });
      $("#costs > div.loading").hide();
      $("#costs > table").show("slow");
    },
    error: function() {
      restore_loading_state("#costs");
    }
  });
}

// --- forex -----------------------------------------------------------------

function update_forex() {
  $("#forex > div.loading").show();
  $("#forex > table").hide();
  $.ajax({
    type: "GET",
    url: "/forex",
    success: function(data) {
      clear_rows("#forex_table");
      $.each(data, function(currency, balance) {
        $("#forex_table tbody").append(`<tr><td>${currency}</td><td>${balance}</td></tr>`);
      });
      $("#forex > div.loading").hide();
      $("#forex > table").show("slow");
    },
    error: function() {
      restore_loading_state("#forex");
    }
  }
  );
}

// --- liquidity -------------------------------------------------------------

function update_liquidity() {
  $("#liquidity > div.loading").show();
  $("#liquidity > table").hide();
  $.ajax({
    type: "GET",
    url: "/liquidity",
    success: function(data) {
      clear_rows("#liquidity_table");
      $.each(data, function(instrument, vals) {
        var contracts = "";
        var risk = "";
        if (vals["contracts"] < 100) {
          contracts = `<td class="red">${vals["contracts"]}</td>`;
        } else {
          contracts = `<td>${vals["contracts"]}</td>`;
        }
        if (vals["risk"] < 1.5) {
          risk = `<td class="red">${vals["risk"].toFixed(1)}</td>`;
        } else {
          risk = `<td>${vals["risk"].toFixed(1)}</td>`;
        }
        $("#liquidity_table tbody").append(
          `<tr><td>${instrument}</td>${contracts}
          ${risk}</tr>`
        );
      });
      $("#liquidity > div.loading").hide();
      $("#liquidity > table").show("slow");
    },
    error: function() {
      restore_loading_state("#liquidity");
    }
  }
  );
}

// --- P&L -------------------------------------------------------------------

function update_pandl() {
  $("#pandl > div.loading").show();
  $("#pandl > table").hide();
  $.ajax({
    type: "GET",
    url: "/pandl",
    success: function(data) {
      clear_rows("#pandl_instrument_table");
      clear_rows("#pandl_strategy_table");
      clear_rows("#pandl_class_table");
      $.each(data["pandl_for_instruments_across_strategies"], function(k, v) {
        $("#pandl_instrument_table tbody").append(`<tr>
          <td>${v["codes"]}</td><td>${v["pandl"].toFixed(2)}</td></tr>`);
      });

      $.each(data["strategies"], function(k, v) {
        $("#pandl_strategy_table tbody").append(`<tr>
          <td>${v["codes"]}</td><td>${v["pandl"].toFixed(2)}</td></tr>`);
      });

      $.each(data["sector_pandl"], function(k, v) {
        $("#pandl_class_table tbody").append(`<tr>
          <td>${v["codes"]}</td><td>${v["pandl"].toFixed(2)}</td></tr>`);
      });
      $("#pandl > div.loading").hide();
      $("#pandl > table").show("slow");
    },
    error: function() {
      restore_loading_state("#pandl");
    }
  }
  );
}

// --- processes -------------------------------------------------------------

function update_processes() {
  $("#processes > div.loading").show();
  $("#processes > table").hide();
  $.ajax({
    type: "GET",
    url: "/processes",
    success: function(data) {
      clear_rows("#processes_config");
      clear_rows("#processes_status");
      clear_rows("#processes_prices");
      if (data['process']['run_stack_handler']['running'] == 'running') {
        set_traffic_light('#stack-tl', "green");
      } else if (data['process']['run_stack_handler']['running'] == 'crashed') {
        set_traffic_light('#stack-tl', "red");
      } else {
        set_traffic_light('#stack-tl', "orange");
      }
      $("#processes_config tbody").append(`
        <tr><td>Monitoring target</td><td>${data['config']['monitor']}</td></tr>
        <tr><td>Mongo DB</td><td>${data['config']['mongo']}</td></tr>
        <tr><td>IB gateway</td><td>${data['config']['ib']}</td></tr>
        `)
      $.each(data['process'], function(process, stat) {
        var running = stat['running']
        if (running == 'crashed') {
        $("#processes_status tbody").append(`
          <tr><td>${process}</td>
          <td>${stat['status']}</td>
          <td class="red">${running}</td>
          <td>${stat['PID']}</td>
          <td>${stat['previous_process']}</td>
          <td>${stat['prev_process']}</td>
          <td>${stat['start_time']}</td>
          <td>${stat['end_time']}</td>
          <td>${stat['start']}</td>
          <td>${stat['end']}</td>
          </tr>`);
        } else {
          $("#processes_status tbody").append(`
          <tr><td>${process}</td>
          <td>${stat['status']}</td>
          <td>${running}</td>
          <td>${stat['PID']}</td>
          <td>${stat['previous_process']}</td>
          <td>${stat['prev_process']}</td>
          <td>${stat['start_time']}</td>
          <td>${stat['end_time']}</td>
          <td>${stat['start']}</td>
          <td>${stat['end']}</td>
          </tr>`);
        }
      }
      );
      var now = new Date();
      var most_recent_diff = 999;
      var most_recent_date = new Date();
      // Find the most recent update
      $.each(data['price'], function(instrument, update) {
        var date = new Date(update['last_update']);
        var days = (now.getTime() - date.getTime()) / (1000 * 24 * 60 * 60);
        if (days < most_recent_diff) {
          most_recent_diff = days;
          most_recent_date = date;
        }
      });

      var price_overall = 'green';
      $.each(data['price'], function(idx, update) {
        var str = update['last_update'];
        var date = new Date(str);
        var diff = (most_recent_date.getTime() - date.getTime()) / (1000 * 24 * 60 * 60);  // days
        var short_date = str.substring(5,7) + "/" + str.substring(8,10) + " " + str.substring(11,19);
        if (most_recent_diff > 1.0) {
          price_overall = "orange";
        }
        if (diff <= 1.0)
        {
          $("#processes_prices tbody").append(`
          <tr>
            <td>${update['index']}</td>
            <td>${short_date}</td>
          </tr>
          `);
        } else {
          $("#processes_prices tbody").append(`
          <tr>
            <td>${update['index']}</td>
            <td class="red">${short_date}</td>
          </tr>
          `);
          price_overall = 'red';
        }
      });
      set_traffic_light('#prices-tl', price_overall);
      $("#processes > div.loading").hide();
      $("#processes > table").show("slow");
    },
    error: function() {
      restore_loading_state("#processes");
    }
  }
  );
}

// --- reconciliation --------------------------------------------------------

function update_reconcile() {
  $("#reconciliation > div.loading").show();
  $.ajax({
    type: "GET",
    url: "/reconcile",
    success: function(data) {
      clear_rows("#reconcile_strategy");
      clear_rows("#reconcile_contract");
      var overall = "green";
      $.each(data['optimal'], function(contract, details) {
	if (details['optimal']['upper_position']) {
	  // Static strategy
          var optimal = `${details['optimal']['lower_position'].toFixed(1)} / ${details['optimal']['upper_position'].toFixed(1)}`;
	} else {
	  var optimal = details['optimal'];
	}

        if (details['breaks']) {
        $("#reconcile_strategy tbody").append(`
          <tr><td>${contract}</td>
          <td class="red">${details['current']}</td>
          <td class="red">${optimal}</td>
          </tr>`);
          overall = "orange";
        } else {
        $("#reconcile_strategy tbody").append(`
          <tr><td>${contract}</td>
          <td>${details['current']}</td>
          <td>${optimal}</td>
          </tr>`);
        }
      }
      );
      $.each(data['my'], function(contract, details) {
        var line = `<tr><td>${details['instrument_code']}</td>
          <td>${details['contract_date']}</td>`;
        if (details['position'] != data['ib'][contract]['position']) {
          line += `<td class="red">${details['position']}</td>
            <td class="red">${data['ib'][contract]['position']}</td>`;
          overall = "red";
        } else {
          line += `<td>${details['position']}</td>
            <td>${data['ib'][contract]['position']}</td>`;
        }
        $("#reconcile_contract tbody").append(line);
      }
      );
      set_traffic_light('#breaks-tl', overall);
      if (data['gateway_ok']) {
        set_traffic_light('#gateway-tl', "green");
      } else {
        set_traffic_light('#gateway-tl', "red");
      }
      $("#reconciliation > div.loading").hide();
      $("#reconciliation > table").show("slow");
    },
    error: function() {
      restore_loading_state("#reconciliation");
    }
  }
  );
}

// --- risk ------------------------------------------------------------------

function update_risk() {
  $("#risk > div.loading").show();
  $("#risk > table").hide();
  $.ajax({
    type: "GET",
    url: "/risk",
    success: function(data) {
      clear_rows("#risk_table");
      clear_rows("#risk_corr_table");
      clear_rows("#risk_details_table");
      var cols = "<td></td>";
      $.each(data["correlations"], function(k, v) {
        var row = `<td>${k}</td>`;
        cols += row;
        $.each(v, function(_, corr) {
          row += `<td>${corr.toFixed(3)}</td>`
        });
        $("#risk_corr_table tbody").append(`<tr>${row}</tr>`);
      });
      $("#risk_corr_table tbody").prepend(`<tr>${cols}</tr>`);

      $.each(data["strategy_risk"], function(k,v) {
        $("#risk_table tbody").append(`<tr><td>${k}</td><td>${(v['risk']).toFixed(1)}</td></tr>`);
      });

      $.each(data["instrument_risk"], function(k,v) {
        $("#risk_details_table tbody").append(`<tr><td>${k}</td>
          <td>${v["daily_price_stdev"].toFixed(1)}</td>
          <td>${v["annual_price_stdev"].toFixed(1)}</td>
          <td>${v["price"].toFixed(1)}</td>
          <td>${v["daily_perc_stdev"].toFixed(1)}</td>
          <td>${v["annual_perc_stdev"].toFixed(1)}</td>
          <td>${v["point_size_base"].toFixed(1)}</td>
          <td>${v["contract_exposure"].toFixed(1)}</td>
          <td>${v["daily_risk_per_contract"].toFixed(1)}</td>
          <td>${v["annual_risk_per_contract"].toFixed(1)}</td>
          <td>${v["position"].toFixed(0)}</td>
          <td>${v["capital"].toFixed(1)}</td>
          <td>${v["exposure_held_perc_capital"].toFixed(1)}</td>
          <td>${v["annual_risk_perc_capital"].toFixed(1)}</td>
          </tr>`);
      });
      $("#risk > div.loading").hide();
      $("#risk > table").show("slow");
    },
    error: function() {
      restore_loading_state("#risk");
    }
  }
  );
}

// --- rolls -----------------------------------------------------------------

function update_rolls() {
  $("#rolls > div.loading").show();
  $("#rolls > table").hide();
  $.ajax({
    type: "GET",
    url: "/rolls",
    success: function(data) {
      clear_rows("#rolls_status");
      var overall = "green";
      $.each(data, function(contract, details) {
        var buttons = "";
        $.each(details['allowable'], function(_, option) {
          buttons += `<button onClick="roll_post('${contract}', '${option}')">${option}</button>`
        });
        var relative_volume = parseFloat(details['relative_volume_fwd']);
        var relative_volume_str = isNaN(relative_volume) ? "" : relative_volume.toFixed(3);
        $("#rolls_status tbody").append(`
          <tr id="rolls_${contract}"><td>${contract}</td>
          <td>${display_value(details['status'])}</td>
          <td>${display_value(details['roll_expiry'])}</td>
          <td>${display_value(details['carry_expiry'])}</td>
          <td>${display_value(details['price_expiry'])}</td>
          <td>${display_value(details['contract_priced'])}</td>
          <td>${display_value(details['contract_fwd'])}</td>
          <td>${relative_volume_str}</td>
          <td>${display_value(details['position_priced'])}</td>
          <td>${buttons}</td>
          </tr>`);
        if (details['roll_expiry'] < 0) {
          overall = "red";
        } else if (details['roll_expiry'] < 5 && overall != "red") {
          overall = "orange";
        }
      }
      );
      set_traffic_light("#rolls-tl", overall);
      $("#rolls > div.loading").hide();
      $("#rolls > table").show("slow");
    },
    error: function() {
      restore_loading_state("#rolls");
    }
  });
}

// --- strategy --------------------------------------------------------------

function update_strategy() {
  $("#strategy > div.loading").show();
  $("#strategy > table").hide();
  $.ajax({
    type: "GET",
    url: "/strategy",
    success: function(data) {
      $.each(data, function(k, v) {
      });
      $("#strategy > div.loading").hide();
      $("#strategy > table").show("slow");
    },
    error: function() {
      restore_loading_state("#strategy");
    }
  }
  );
}

// --- trades ----------------------------------------------------------------

function update_trades() {
  $("#trades > div.loading").show();
  $("#trades > table").hide();
  $.ajax({
    type: "GET",
    url: "/trades",
    success: function(data) {
      clear_rows("#trades_overview_table");
      clear_rows("#trades_delay_table");
      clear_rows("#trades_slippage_table");
      clear_rows("#trades_vol_slippage_table");
      clear_rows("#trades_cash_slippage_table");
      $.each(data["overview"], function(k, v) {
        $("#trades_overview_table tbody").append(`<tr>
          <td>${k}</td>
          <td>${v["instrument_code"]}</td>
          <td>${v["contract_date"]["date_str"]}</td>
          <td>${v["strategy_name"]}</td>
          <td>${v["fill_datetime"]}</td>
          <td>${v["fill"]}</td>
          <td>${v["filled_price"]}</td>
          </tr>`)
      });
      $.each(data["delays"], function(k, v) {
        $("#trades_delay_table tbody").append(`<tr>
          <td>${k}</td>
          <td>${v["instrument_code"]}</td>
          <td>${v["strategy_name"]}</td>
          <td>${v["parent_reference_datetime"]}</td>
          <td>${v["submit_datetime"]}</td>
          <td>${v["fill_datetime"]}</td>
          <td>${v["submit_minus_generated"]}</td>
          <td>${v["filled_minus_submit"]}</td>
          </tr>`)
      });
      $.each(data["raw_slippage"], function(k, v) {
        $("#trades_slippage_table tbody").append(`<tr>
          <td>${k}</td>
          <td>${v["instrument_code"]}</td>
          <td>${v["strategy_name"]}</td>
          <td>${v["trade"]}</td>
          <td>${v["parent_reference_price"]}</td>
          <td>${v["parent_limit_price"]}</td>
          <td>${v["mid_price"]}</td>
          <td>${v["side_price"]}</td>
          <td>${v["limit_price"]}</td>
          <td>${v["filled_price"]}</td>
          <td>${parseFloat(v["delay"]).toPrecision(3)}</td>
          <td>${parseFloat(v["bid_ask"]).toPrecision(3)}</td>
          <td>${parseFloat(v["execution"]).toPrecision(3)}</td>
          <td>${parseFloat(v["versus_limit"]).toPrecision(3)}</td>
          <td>${v["versus_parent_limit"]}</td>
          <td>${parseFloat(v["total_trading"]).toPrecision(3)}</td>
          </tr>`)
      });
      $.each(data["vol_slippage"], function(k, v) {
        $("#trades_vol_slippage_table tbody").append(`<tr>
          <td>${k}</td>
          <td>${v["instrument_code"]}</td>
          <td>${v["strategy_name"]}</td>
          <td>${v["trade"]}</td>
          <td>${v["last_annual_vol"]}</td>
          <td>${v["delay_vol"]}</td>
          <td>${v["bid_ask_vol"]}</td>
          <td>${v["execution_vol"]}</td>
          <td>${v["versus_limit_vol"]}</td>
          <td>${v["versus_parent_limit_vol"]}</td>
          <td>${v["total_trading_vol"]}</td>
          </tr>`)
      });
      $.each(data["cash_slippage"], function(k, v) {
        $("#trades_cash_slippage_table tbody").append(`<tr>
          <td>${k}</td>
          <td>${v["instrument_code"]}</td>
          <td>${v["strategy_name"]}</td>
          <td>${v["trade"]}</td>
          <td>${v["value_of_price_point"]}</td>
          <td>${v["delay_cash"]}</td>
          <td>${v["bid_ask_cash"]}</td>
          <td>${v["execution_cash"]}</td>
          <td>${v["versus_limit_cash"]}</td>
          <td>${v["versus_parent_limit_cash"]}</td>
          <td>${v["total_trading_cash"]}</td>
          </tr>`)
      });
      $("#trades > div.loading").hide();
      $("#trades > table").show("slow");
    },
    error: function() {
      restore_loading_state("#trades");
    }
  }
  );
}

// --- roll actions ----------------------------------------------------------

function roll_post(instrument, state, confirmed = false) {
  // Disable all the buttons to avoid multiple presses
  $("#rolls button").each(function(_, btn) {
    btn.disabled = true;
  });
  $("#rolls > div.loading").show();
  $("#roll_prices_single > tbody").empty();
  $("#roll_prices_multiple > tbody").empty();
  $.ajax({
    type: "POST",
    url: "/rolls",
    data: {'instrument': instrument, 'state': state, 'confirmed': confirmed},
    success: function(data)
    {
      $("#roll_prices").addClass("hidden");
      if (data["new_state"] == "Roll_Adjusted") {
        // Lots has changed so refresh everything
        update_rolls();
      } else if (data["single"]){
        // Populate the div to show the new prices
        $("#roll_prices").removeClass("hidden");
        $("#roll_instrument_name").text("Proposed Adjusted Prices - " + instrument);
        $.each(data['single'], function(date, val) {
          current = val['current'] ? val['current'] : "";
          $("#roll_prices_single tbody").append(`
            <tr>
            <td>${date}</td>
            <td>${current}</td>
            <td>${val['new']}</td>
            </tr>`);
        });
        $.each(data['multiple'], function(date, val) {
          current = val['current'] ? val['current'] : {'CARRY': '', 'PRICE': '', 'FORWARD': ''};
          $("#roll_prices_multiple tbody").append(`
            <tr>
            <td>${date}</td>
            <td>${val['new']['CARRY_CONTRACT']}</td>
            <td>${current['CARRY']}</td>
            <td>${val['new']['CARRY']}</td>
            <td>${val['new']['PRICE_CONTRACT']}</td>
            <td>${current['PRICE']}</td>
            <td>${val['new']['PRICE']}</td>
            <td>${val['new']['FORWARD_CONTRACT']}</td>
            <td>${current['FORWARD']}</td>
            <td>${val['new']['FORWARD']}</td>
            </tr>`);
        });
        $("#roll_confirm").remove();
        $("#roll_prices").append(`<div id="roll_confirm"><button onClick="roll_post('${instrument}', '${state}', true)">${state}</button><br><br></div>`);
        $("#roll_prices").display = true;
      } else if (data["allowable"]) {
        // Only need to update this line
        var buttons = "";
        $.each(data['allowable'], function(_, option) {
          buttons += `<button onClick="roll_post('${instrument}', '${option}')">${option}</button>`
        });
        $("#rolls_" + instrument).find("td:eq(1)").html(data["new_state"]);
        $("#rolls_" + instrument).find("td:eq(9)").html(buttons);
      }

      $("#rolls button").each(function(_, btn) {
        btn.disabled = false;
      });
      $("#rolls > div.loading").hide();
    }
  });
}

// --- refresh orchestration -------------------------------------------------

var TAB_UPDATERS = {
  tab_rolls: update_rolls,
  tab_processes: update_processes,
  tab_pandl: update_pandl,
  tab_trades: update_trades,
  tab_reconciliation: update_reconcile,
  tab_strategy: update_strategy,
  tab_risk: update_risk,
  tab_liquidity: update_liquidity,
  tab_costs: update_costs,
  tab_forex: update_forex
};

function active_tab_id() {
  return $("input[name='tabs']:checked").attr("id");
}

function update_active_tab() {
  var updater = TAB_UPDATERS[active_tab_id()];
  if (updater) {
    updater();
  }
}

// Skip a refresh cycle if the previous one is still running, so that slow
// endpoints cannot build up overlapping requests.
var refresh_in_progress = false;

function refresh_dashboard() {
  if (refresh_in_progress) {
    return;
  }
  refresh_in_progress = true;

  // Traffic light widgets and the always visible tables first.
  var updaters = [update_capital, update_processes, update_reconcile, update_rolls];
  var tab_updater = TAB_UPDATERS[active_tab_id()];
  if (tab_updater && updaters.indexOf(tab_updater) === -1) {
    updaters.push(tab_updater);
  }
  updaters.forEach(function(updater) {
    updater();
  });
}

// Surface endpoint failures instead of silently showing stale or blank tables.
var pending_requests = 0;
var cycle_errors = [];

$(document).ajaxSend(function() {
  pending_requests += 1;
});

$(document).ajaxError(function(event, jqXHR, settings, thrownError) {
  cycle_errors.push(settings.url + " (" + jqXHR.status + " " + (thrownError || jqXHR.statusText) + ")");
});

$(document).ajaxComplete(function() {
  pending_requests -= 1;
  if (pending_requests > 0) {
    return;
  }
  refresh_in_progress = false;
  if (cycle_errors.length) {
    show_dashboard_message("Some requests failed: " + cycle_errors.join(", "));
    cycle_errors = [];
  } else {
    clear_dashboard_message();
    mark_updated();
  }
});

$(document).ready(function() {
  $("input[name='tabs']").on("change", update_active_tab);

  refresh_dashboard();
  if (DASHBOARD_REFRESH_MS > 0) {
    setInterval(refresh_dashboard, DASHBOARD_REFRESH_MS);
  }
});
