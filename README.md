# Solar Payback

**When have my solar panels and battery paid for themselves?**

Solar Payback works out how much your solar panels and home battery have saved, how much of the purchase price is paid back, and when everything has paid for itself. A card with a graph is included.

[Svenska instruktioner](README.sv.md)

![Solar Payback card](images/card.png)

## Get started

It takes about five minutes. You need [HACS](https://hacs.xyz) and an inverter or battery that already shows up in Home Assistant.

**1. Install**

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=TimmyUll&repository=ha-solar-payback&category=integration)

Press the button, then **Download**, and restart Home Assistant.

**2. Add the integration**

[![Add Solar Payback](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solar_payback)

Answer the questions. All you need at hand is:

- **What the system cost** (after any grants) and **when it started**.
- **The house consumption**: pick the sensor from your inverter. It is often called something with *load* or *consumption*. [Help finding it](#find-the-house-consumption).
- **The grid fee per kWh** from your grid company's invoice. Not sure? Enter 0 now and change it later.

With Tibber everything else is found automatically. Otherwise pick bought and sold electricity from the Energy dashboard ([how](#without-tibber)).

**3. Add the card**

Edit a dashboard, press **Add card** and search for **Solar Payback**.

**4. Do you get Grid Rewards or another monthly reward?**

Turn it on during setup. Then press **+ Add** on the card once a month and type the amount. The card reminds you when a month is missing.

Done! Everything is calculated locally in your Home Assistant and nothing is sent anywhere.

## More help

Everything below is optional. Open what you need.

<a id="find-the-house-consumption"></a>
<details>
<summary><b>Find the house consumption (by brand)</b></summary>

The house consumption is **everything your house uses**, no matter whether it comes from the panels, the battery or the grid. It must be an energy sensor in **kWh that keeps counting up** (not power in W).

### How to look for it

1. Go to **Settings → Devices & services** and open your inverter or battery integration.
2. Look for an energy sensor with a name like *load*, *consumption*, *house consumption*, *home energy* or *total load*. It should have a unit of kWh and a value that only goes up (a lifetime total or a daily total that resets at midnight both work).
3. Check that it has statistics: open the sensor and click the graph. If you see a bar chart or a smooth line over several days, it works.

### Common brands

Entity names differ between integrations and versions, so treat these as hints for what to look for.

| Brand | Integration | What to look for |
|---|---|---|
| **SAJ** (H1, H2, HS2, HS3) | SAJ Modbus integrations | A *total load* or *load energy* sensor in kWh. |
| **Huawei** (SUN2000 + LUNA2000) | Huawei Solar (HACS) | Usually no direct house energy. Use the formula below with the power meter's import/export, the inverter's total yield and the battery's charge/discharge. |
| **Tesla Powerwall** | Powerwall (built in) | The **Load import** energy sensor. |
| **SolarEdge** | SolarEdge (built in) or SolarEdge Modbus Multi | A *consumed* or *consumption* energy sensor if you have a SolarEdge meter, otherwise the formula below. |
| **Fronius** | Fronius (built in) | *Power load* is power (W), usually negative. Make it positive with a template and turn it into kWh with an integral helper, see below. |
| **Victron** (Cerbo GX, MultiPlus) | Victron GX Modbus / MQTT | *AC consumption* power (W). Turn it into kWh with an integral helper. |
| **Enphase** | Enphase Envoy (built in) | *Lifetime energy consumption*, if consumption CTs are installed. |
| **Sungrow** | Sungrow Modbus (HACS) | A *total load* or *load energy consumption* sensor. |
| **GoodWe** | GoodWe (built in) | An energy sensor for house or load consumption. If there is only *House consumption* power (W), use an integral helper. |
| **Deye, Sunsynk, Solis, Growatt** | Solarman, Sunsynk, Growatt and others | A *total load consumption* or *load energy* sensor. |

If you are unsure, compare one day's value with the inverter's own app. They should be close.

### If there is no house consumption sensor: create one

**Option A: you have a power sensor (W) for the house.** Turn it into energy with an integral helper:

1. Go to **Settings → Devices & services → Helpers → Create helper → Integral sensor**.
2. Name it, for example *House consumption*.
3. Input sensor: the house's power sensor.
4. Integration method: **Left**. Metric prefix: **k (kilo)**. Time unit: **Hours**.
5. Click **Submit**. You now have a kWh sensor with statistics.

If the power sensor is negative (as with Fronius), first create a template sensor (**Helpers → Create helper → Template → Template sensor**) with the state `{{ states('sensor.your_power_load') | float(0) | abs }}`, unit **W**, device class **Power**, state class **Measurement**, and use that one instead.

**Option B: calculate it from the other energy sensors.** The house uses what comes in minus what goes out:

```
house = bought from grid + solar production + battery discharge − sold to grid − battery charge
```

For hybrid inverters where the inverter's AC output already includes the battery (common for Huawei, SAJ, GoodWe, Sungrow and Deye), this is often simpler:

```
house = bought from grid + inverter AC output − sold to grid
```

Create it as a template sensor (**Helpers → Create helper → Template → Template sensor**):

- State, for example: `{{ states('sensor.grid_import_total') | float(0) + states('sensor.solar_total') | float(0) + states('sensor.battery_discharge_total') | float(0) - states('sensor.grid_export_total') | float(0) - states('sensor.battery_charge_total') | float(0) }}`
- Unit **kWh**, device class **Energy**, state class **Total increasing**.

Use lifetime totals (not daily totals) in the formula so the result never drops at midnight.

**Remember:** a sensor you create now only has statistics from today. The days before are estimated, see *How far back can it go?* below.

</details>

<a id="without-tibber"></a>
<details>
<summary><b>Without Tibber</b></summary>

1. Go to **Settings → Dashboards → Energy** and make sure **Grid consumption** (and **Return to grid** if you sell) are set up.
2. Choose how the cost is calculated there: **Use an entity with current price** (for example Nord Pool) or a fixed price. Home Assistant then creates statistics for the cost of bought energy and the compensation for sold energy. Those are the ones you pick during setup.
3. If you'd rather not use the Energy dashboard, install a price integration such as **Nord Pool** (built in) and pick its price sensor during setup.

</details>

<details>
<summary><b>All setup questions</b></summary>

1. Go to **Settings → Devices & services → Add integration** and search for **Solar Payback**.
2. **Your solar system**
   - *Name*: anything, for example *Solar*.
   - *Purchase price*: what you actually paid, after any tax deduction or subsidy (in Sweden: after *grönt avdrag*).
   - *Start date*: the day the system started, for example the first day you sold electricity.
3. **Bought and sold electricity**: choose **Tibber** if it is offered, otherwise pick the statistics described under *Without Tibber*.
4. **The house's consumption**: pick the sensor described under *Find the house consumption*. With Tibber you can also pick an electricity price sensor as a backup for hours where Tibber has no cost.
5. **Grid fees and settings**
   - *Grid fee per bought kWh*: look at your grid company's invoice. Add the transfer fee and the energy tax per kWh, and include VAT. Example: transfer 0.25 + energy tax 0.40 excl. VAT = 0.65 × 1.25 = **0.8125** per kWh. This is what you avoid paying for every kWh you don't buy. The fixed subscription fee doesn't change and is not included.
   - *Grid compensation per sold kWh*: what the grid company pays you per exported kWh (often a few cents/öre, without VAT). 0 if none.
   - *Supplier markup per kWh*: only used when the hourly cost is missing and the spot price is used instead. Excluding VAT.
   - *VAT factor*: 1.25 for 25 % VAT.
   - *Forecast based on the last days*: 60 is a good start. A longer period gives a calmer forecast.
   - *I get a monthly reward*: turn on if a service pays you each month, for example Tibber Grid Rewards. Leave off if you get no such payment: the card then only shows solar, battery and sold electricity, and there is no monthly reminder.
   - *Name of the monthly reward*: shown on the card, for example *Grid Rewards*.
   - *Monthly rewards are entered including VAT*: leave off if your invoice shows the reward excluding VAT. Then the VAT it saves is added.
6. Click **Submit**. The sensors appear after a few seconds.

You can change everything except the data source later under **Settings → Devices & services → Solar Payback → Configure**.

</details>

<details>
<summary><b>Monthly reward: more ways and a reminder</b></summary>

First turn on *I get a monthly reward* during setup (or later under **Configure**).

If you get paid for letting your battery help the grid (for example Tibber Grid Rewards, or a support-services/FCR payout from another provider), enter the amount once a month:

1. Go to **Developer tools → Actions**.
2. Choose **Solar Payback: Set monthly reward**.
3. Fill in *Month* (for example `2026-09`) and *Amount* (as a positive number).
4. Click **Perform action**.

**Easiest:** open the card, tap **+ Add Grid Rewards**, pick the month, type the amount and tap **Save**. When last month is missing, the card shows a reminder at the top that opens the same form.

Or in YAML:

```yaml
action: solar_payback.set_monthly_reward
data:
  month: "2026-09"
  amount: 450.00
```

**Tibber tip:** In the Tibber app under *Rewards*, Grid Rewards are split between the home battery and an electric car. If you only want to count what the battery earns, use the battery's amount. The invoice only shows the total.

**Reminder:** the binary sensor *Monthly reward missing* turns on when last month has no value. An automation that reminds you on the 5th of each month:

```yaml
alias: Remind me to enter the monthly reward
triggers:
  - trigger: time
    at: "09:00:00"
conditions:
  - condition: template
    value_template: "{{ now().day == 5 }}"
  - condition: state
    entity_id: binary_sensor.solar_monthly_reward_missing
    state: "on"
actions:
  - action: notify.notify
    data:
      message: "Enter last month's Grid Rewards in Solar Payback."
```

To remove a month, use **Solar Payback: Remove monthly reward**.

</details>

<details>
<summary><b>Card options</b></summary>

1. Open a dashboard, click **Edit** and **Add card**.
2. Search for **Solar Payback**.
3. Pick the *Saved so far* sensor.

Or in YAML:

```yaml
type: custom:solar-payback-card
entity: sensor.solar_saved_so_far
```

| Option | Default | Description |
|---|---|---|
| `entity` | | The *Saved so far* sensor (required) |
| `title` | *Solar and battery* | Title on the card |
| `collapsed` | `true` | Start collapsed. Tap the top of the card to show the graph. |

The card follows your theme and is shown in Swedish or English depending on your language.

</details>

<details>
<summary><b>How it is calculated</b></summary>

Once an hour the integration reads Home Assistant's long-term statistics from the start date and values every hour:

| Part | How it is valued |
|---|---|
| **Solar and battery in the house** | Energy the house used but did not buy from the grid (it came from the panels or the battery). It is worth what it would have cost: that hour's price plus the grid fee you avoid. |
| **Sold electricity** | What your supplier paid for the energy you exported, plus any compensation from the grid company per sold kWh. |
| **Monthly reward** | Money a service pays you each month, for example Tibber Grid Rewards for letting your battery help the grid. You enter it once a month. |

Everything is added up per day. The forecast assumes you keep saving at the same pace as the last 60 days (you can change the number of days).

The calculation uses the formula *house consumption − bought energy*, so it counts both the solar energy used directly and the energy that went through the battery. Charging the battery from the grid at night and using it in the evening is counted correctly too: the bought energy is subtracted at the price of the hour it was bought.

### What is used

All of these must be sensors or statistics with **long-term statistics** in Home Assistant (anything that shows up in the Energy dashboard has them).

| Data | Required? | Typical source |
|---|---|---|
| Energy bought from the grid (kWh) | Yes | Tibber, the electricity meter (P1/HAN port), or the inverter's grid meter |
| Cost of bought energy | One of these two | Tibber, or the cost sensor the Energy dashboard creates |
| Electricity price per kWh | | Nord Pool, Tibber's price sensor, Energi Data Service, ENTSO-e |
| Energy sold to the grid (kWh) | If you sell | Tibber, the meter, or the inverter |
| Revenue for sold energy | No | Tibber, or the compensation sensor the Energy dashboard creates. If missing, sold energy is valued at the electricity price. |
| **House consumption (kWh)** | Yes | The inverter or battery system. See [Find the house consumption](#find-the-house-consumption). |
| Grid fee per bought kWh | Recommended | Your grid company's invoice (entered as a number) |
| Monthly reward | No | Your supplier's app or invoice (entered each month) |

</details>

<details>
<summary><b>How far back can it go?</b></summary>

Home Assistant keeps long-term statistics forever, so nothing disappears once it is there. How far back you get depends on when each source started recording:

- **Tibber** loads its history back in time by itself, often well before you added it to Home Assistant. Bought and sold energy and cost are usually complete from day one.
- **The inverter's house consumption** only exists from the day you added the inverter integration to Home Assistant. It can't be fetched backwards.
- **Days before the house consumption existed** are estimated from the average of the first 30 days with data. Those months are marked with * on the card. The longer the system has been running, the less these estimates matter.
- **Monthly rewards** are not in any API we know of. You enter them by hand from the app or invoices, and you can enter old months too, as far back as you have the numbers. Months you leave out are estimated from the latest month you entered.

No access to old invoices is needed. The only thing you look up by hand is the monthly reward.

</details>

<details>
<summary><b>Sensors</b></summary>

| Sensor | Description |
|---|---|
| Saved so far | Total savings since the start date. Its attributes hold the data for the card. |
| Paid back | Share of the purchase price earned back (%) |
| Remaining | Amount left to earn back |
| Payback date | Estimated date when the system has paid for itself |
| Payback time | Years from start to the payback date |
| Saved per day | Average for the last days (the forecast pace) |
| Saved this month | Savings in the current month |
| Monthly rewards total | Sum of all monthly rewards (only with monthly reward on) |
| Monthly reward missing | On when last month has no reward value (only with monthly reward on) |

</details>

<details>
<summary><b>Questions and limitations</b></summary>

- **The forecast doesn't know about seasons.** In summer it looks faster, in winter slower. A longer forecast period (for example 365 days once you have a year of data) evens it out.
- **Energy tax reductions and other subsidies** per sold kWh can be included in the grid compensation if they apply to you.
- **Fixed fees** (subscriptions, monthly fees) are not included since they don't change with the system.
- **Several systems or houses?** Add the integration once per system.
- **Privacy:** everything is calculated locally in your Home Assistant. Nothing is sent anywhere.

</details>

<details>
<summary><b>Install without the button</b></summary>

You need [HACS](https://hacs.xyz) installed.

1. Open **HACS** in Home Assistant.
2. Click the three dots in the top right corner and choose **Custom repositories**.
3. Paste the address of this repository, choose type **Integration** and click **Add**.
4. Search for **Solar Payback** in HACS, open it and click **Download**.
5. Restart Home Assistant (**Settings → System → Restart**).

The card is included and loads automatically. You don't need to install it separately.

</details>

## License

[MIT](LICENSE)
