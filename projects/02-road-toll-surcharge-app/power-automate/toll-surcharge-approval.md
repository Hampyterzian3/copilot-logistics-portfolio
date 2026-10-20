# Flow: TollSurchargeApproval

Tiered approval of a surcharge proposal. Solution-aware instant cloud flow, called from the canvas app.

## Trigger
**Power Apps (V2)** with input `ProposalId` (text).

## Actions
1. **Get a row by ID** (Dataverse): table `SurchargeProposals`, row id `triggerBody()['text']`, expand `cl_customer($select=cl_code,cl_name,_cl_accountowner_value)`.
2. **Get a row by ID** (Dataverse): `Users`, id `outputs('Get_proposal')?['body/cl_customer/_cl_accountowner_value']`, to obtain the manager's email.
3. **Compose `Tier`**: `outputs('Get_proposal')?['body/cl_tier@OData.Community.Display.V1.FormattedValue']`
4. **Compose `Facts`** (used in every card):
   ```
   concat('Customer: ', outputs('Get_proposal')?['body/cl_customer/cl_code'],
          ' | Surcharge: EUR ', formatNumber(outputs('Get_proposal')?['body/cl_surchargeeur'], 'N2', 'en-GB'),
          ' | Increase: ', formatNumber(outputs('Get_proposal')?['body/cl_increasepct'], 'N2'), '%',
          ' | Margin: ', formatNumber(outputs('Get_proposal')?['body/cl_marginpctbefore'], 'N1'), '% to ',
          formatNumber(outputs('Get_proposal')?['body/cl_marginpctafter'], 'N1'), '%')
   ```
5. **Switch on `outputs('Tier')`**
   - **Case `Auto-approved`**: Update row `cl_status = Approved`, `cl_approvalcomments = 'Approved by policy (under auto thresholds)'`. Post message in Teams channel "Toll surcharge log".
   - **Case `Commercial manager`**:
     - **Start and wait for an approval**, type *Approve/Reject - First to respond*, assigned to the account owner email, title `concat('Toll surcharge ', outputs('Get_proposal')?['body/cl_name'])`, details `outputs('Facts')`, item link to the model-driven form.
     - **Condition** `outputs('Approval_CM')?['body/outcome']` equals `Approve`: update row `Approved`, else `Rejected`; comments `first(outputs('Approval_CM')?['body/responses'])?['comments']`.
   - **Default (`Steering committee`)**: sequential stages.
     - Stage 1: approval by the account owner (as above). If `Reject`, update `Rejected` and **Terminate** (Succeeded).
     - Stage 2: **Start and wait for an approval**, type *Approve/Reject - First to respond*, assigned to the steering committee chair and deputy (`parameters('cl_SteeringCommitteeGroup')` members resolved with **List group members**, joined by `;`).
     - Update row with outcome and comments.
6. **Respond to a Power App or flow**: `Status` = the final `cl_status` formatted value.

## Error handling
- Scope `Try` around steps 1-5, scope `Catch` configured to run after *has failed / has timed out*: update the row back to `Draft`, post the error to the flow owner with `result('Try')`.
- Approvals time out after 5 days (`P5D`), then escalate to the steering committee chair.

## Why the tier is recalculated server-side
The app writes the tier, but the flow re-checks it against the environment variables so an edited client cannot downgrade the route:
```
if(or(greater(outputs('Get_proposal')?['body/cl_increasepct'], float(parameters('cl_TierCmMaxPct'))),
      greater(outputs('Get_proposal')?['body/cl_surchargeeur'], float(parameters('cl_TierCmMaxEur')))),
   'Steering committee',
   if(and(lessOrEquals(outputs('Get_proposal')?['body/cl_increasepct'], float(parameters('cl_TierAutoMaxPct'))),
          lessOrEquals(outputs('Get_proposal')?['body/cl_surchargeeur'], float(parameters('cl_TierAutoMaxEur')))),
      'Auto-approved', 'Commercial manager'))
```

---

# Flow: RecalculateShipmentToll

Scheduled (daily 02:00) or on TollRates change. For bulk recalculation of large volumes, the same maths runs as the Python batch `src/toll.py` (Azure Function or Fabric notebook) and writes `cl_tolleur` back with **Upsert** in batches of 1,000.

1. Trigger: **When a row is added, modified or deleted** on `TollRates`, or Recurrence.
2. **List rows** `Shipments` where `cl_tolleur eq null or modifiedon ge @{addDays(utcNow(), -1)}` (paging on, 100,000 threshold).
3. **Apply to each** (concurrency 20): compute toll with the formula from `toll.py`, **Update a row** `cl_tolleur`.
