
import torch
import time
import torch.nn as nn
import matplotlib.pyplot as plt
from tqdm import tqdm
from sklearn.metrics import precision_score, recall_score, f1_score


def train_stage2_model(
        args, 
        train_loader, 
        val_loader,                     
        user_network_stage1, 
        item_network_stage1,
        user_review_network,
        item_review_network,
        co_attentions, 
        fc_layers_stage2, 
        *, 
        bp_gate,
        criterion,
        models_param, 
        optimizer
    ):
    
    # For recording history usage
    t_loss_list_stage2, t_acc_list_stage2 , v_loss_list_stage2, v_acc_list_stage2, v_f1_list_stage2 = [], [], [], [], []
    save_param = {}

    print("-------------------------- STAGE2 START --------------------------")
    for epoch in range(args["epoch_stage2"]):
        
        # ---------- Train ----------
        n_epochs = args["epoch_stage2"]

        # Frozen stage1 models
        user_network_stage1.val()
        item_network_stage1.val()

        # Set stage2 models to train mode
        user_review_network.train()
        item_review_network.train()
        co_attentions.train()
        fc_layers_stage2.train()

        # These are used to record information in training.
        train_loss = []
        train_accs = []
        train_precisions = []
        train_recalls = []
        train_f1s = []

        for batch in tqdm(train_loader):

            # Exacute models
            user_review_emb, item_review_emb, user_review_mask, item_review_mask, user_lda_groups, item_lda_groups, user_mf_emb, item_mf_emb, labels = batch
            u_batch_size, i_batch_size = len(user_review_emb), len(item_review_emb)
            user_arv = user_network_stage1(user_review_emb.to(args["device"]), user_lda_groups.to(args["device"]))
            item_arv = item_network_stage1(item_review_emb.to(args["device"]), item_lda_groups.to(args["device"]))
            urf, urf_1 = user_review_network(user_arv, user_review_mask.to(args["device"]), u_batch_size)
            irf, irf_1 = item_review_network(item_arv, item_review_mask.to(args["device"]), i_batch_size)
            urf, urf_1, irf, irf_1 = bp_gate.apply(urf), bp_gate.apply(urf_1), bp_gate.apply(irf), bp_gate.apply(irf_1)
            w_urf, w_urf_1, w_urf_2, w_urf_3, w_irf, w_irf_1, w_irf_2, w_irf_3 = co_attentions(urf, irf, urf, urf_1, urf_1, irf, irf_1, irf_1)
            
            user_feature = torch.cat((w_urf, user_mf_emb.to(args["device"])), dim=1)
            item_feature = torch.cat((w_irf, item_mf_emb.to(args["device"])), dim=1)
            user_feature_1 = torch.cat((w_urf_1, user_mf_emb.to(args["device"])), dim=1)
            item_feature_1 = torch.cat((w_irf_1, item_mf_emb.to(args["device"])), dim=1)
            user_feature_2 = torch.cat((w_urf_2, user_mf_emb.to(args["device"])), dim=1)
            item_feature_2 = torch.cat((w_irf_2, item_mf_emb.to(args["device"])), dim=1)
            user_feature_3 = torch.cat((w_urf_3, user_mf_emb.to(args["device"])), dim=1)
            item_feature_3 = torch.cat((w_irf_3, item_mf_emb.to(args["device"])), dim=1)

            fc_input = torch.cat((user_feature, item_feature), dim=1)
            fc_input_1 = torch.cat((user_feature_1, item_feature_1), dim=1)
            fc_input_2 = torch.cat((user_feature_2, item_feature_2), dim=1)
            fc_input_3 = torch.cat((user_feature_3, item_feature_3), dim=1)

            logits, soft_label_1, soft_label_2, soft_label_3 = fc_layers_stage2(fc_input, fc_input_1, fc_input_2, fc_input_3)

            if torch.isnan(logits).any() == True:
                print("Warning! Output logits contain NaN")
                logits = torch.nan_to_num(logits, nan=0.0)

            loss =  (args["trade_off_stage2"]*criterion(logits.squeeze(-1), labels.to(args["device"]).float())
                     + (1-args["trade_off_stage2"])*(criterion(logits, (soft_label_1 + soft_label_2 + soft_label_3)/3))) +\
                    (args["trade_off_stage2"]*criterion(soft_label_1.squeeze(-1), labels.to(args["device"]).float())
                     + (1-args["trade_off_stage2"])*(criterion(soft_label_1, (logits + soft_label_2 + soft_label_3)/3))) +\
                    (args["trade_off_stage2"]*criterion(soft_label_2.squeeze(-1), labels.to(args["device"]).float())
                     + (1-args["trade_off_stage2"])*(criterion(soft_label_2, (logits + soft_label_1 + soft_label_3)/3))) +\
                    (args["trade_off_stage2"]*criterion(soft_label_3.squeeze(-1), labels.to(args["device"]).float())
                     + (1-args["trade_off_stage2"])*(criterion(soft_label_3, (logits + soft_label_1 + soft_label_2)/3)))

            loss =  criterion(logits.squeeze(-1), labels.to(args["device"]).float())

            # Gradients stored in the parameters in the previous step should be cleared out first.
            optimizer.zero_grad()

            # Compute the gradients for parameters.
            loss.backward()

            # Clip the gradient norms for stable training.
            grad_norm = nn.utils.clip_grad_norm_(models_param, max_norm=1)

            # Update the parameters with computed gradients.
            optimizer.step()
            
            # Output after sigmoid is greater than 0.5 will be considered as 1, else 0.
            result_logits = torch.where(logits > 0.5, 1, 0)
            labels = labels.to(args["device"])

            # Compute the informations for current batch.
            acc = (result_logits == labels).float().mean()
            precision = precision_score(labels.cpu(), result_logits.cpu(), zero_division=0)
            recall = recall_score(labels.cpu(), result_logits.cpu())
            f1 = f1_score(labels.cpu(), result_logits.cpu())

            # Record the information.
            train_loss.append(loss.item())
            train_accs.append(acc)
            train_precisions.append(precision)
            train_recalls.append(recall)
            train_f1s.append(f1)

        # The average loss and accuracy of the training set is the average of the recorded values.
        train_loss = sum(train_loss) / len(train_loss)
        train_acc = sum(train_accs) / len(train_accs)
        train_precision = sum(train_precisions) / len(train_precisions)
        train_recall = sum(train_recalls) / len(train_recalls)
        train_f1 = sum(train_f1s) / len(train_f1s)

        print(f"[ Train stage2 | {epoch + 1:03d}/{n_epochs:03d} ] loss = {train_loss:.5f}, acc = {train_acc:.4f}, precision = {train_precision:.4f}, recall = {train_recall:.4f}, f1 = {train_f1:.4f}")
        with open('output/history/stage2.csv','a') as file:
            file.write(time.strftime("%m-%d %H:%M")+","+f"train,stage2,{epoch + 1:03d}/{n_epochs:03d},{train_loss:.5f},{train_acc:.4f},{train_precision:.4f},{train_recall:.4f},{train_f1:.4f}" + "\n")

        # ---------- Validation ----------

        # Frozen stage1 models
        user_network_stage1.eval()
        item_network_stage1.eval()

        # Make sure the model is in eval mode so that some modules like dropout are disabled and work normally.
        user_review_network.eval()
        item_review_network.eval()
        co_attentions.eval()
        fc_layers_stage2.eval()

        # These are used to record information in validation.
        valid_loss = []
        valid_accs = []
        valid_precisions = []
        valid_recalls = []
        valid_f1s = []

        # Iterate the validation set by batches.
        for batch in tqdm(val_loader):

            # We don't need gradient in validation.
            # Using torch.no_grad() accelerates the forward process.
            with torch.no_grad():

                # Exacute models       
                user_review_emb, item_review_emb, user_review_mask, item_review_mask, user_lda_groups, item_lda_groups, user_mf_emb, item_mf_emb, labels = batch
                u_batch_size, i_batch_size = len(user_review_emb), len(item_review_emb)
                user_arv = user_network_stage1(user_review_emb.to(args["device"]), user_lda_groups.to(args["device"]))
                item_arv = item_network_stage1(item_review_emb.to(args["device"]), item_lda_groups.to(args["device"]))

                urf = user_review_network(user_arv, user_review_mask.to(args["device"]), u_batch_size)
                irf = item_review_network(item_arv, item_review_mask.to(args["device"]), i_batch_size)
                urf, irf = bp_gate.apply(urf), bp_gate.apply(irf)
                w_urf, w_irf = co_attentions(urf, irf)

                user_feature = torch.cat((w_urf, user_mf_emb.to(args["device"])), dim=1)
                item_feature = torch.cat((w_irf, item_mf_emb.to(args["device"])), dim=1)

                fc_input = torch.cat((user_feature, item_feature), dim=1)
                logits = fc_layers_stage2(fc_input)

                # We can still compute the loss (but not the gradient).
                loss = criterion(logits.squeeze(-1), labels.to(args["device"]).float())

                # Output after sigmoid is greater than 0.5 will be considered as 1, else 0.
                result_logits = torch.where(logits > 0.5, 1, 0).squeeze(dim=-1)
                labels = labels.to(args["device"])

                # Compute the information for current batch.
                acc = (result_logits == labels.to(args["device"])).float().mean()
                precision = precision_score(labels.cpu(), result_logits.cpu(), zero_division=0)
                recall = recall_score(labels.cpu(), result_logits.cpu())
                f1 = f1_score(labels.cpu(), result_logits.cpu())

                # Record the information.
                valid_loss.append(loss.item())
                valid_accs.append(acc)
                valid_precisions.append(precision)
                valid_recalls.append(recall)
                valid_f1s.append(f1)

        # The average loss and accuracy for entire validation set is the average of the recorded values.
        valid_loss = sum(valid_loss) / len(valid_loss)
        valid_acc = sum(valid_accs) / len(valid_accs)
        valid_precision = sum(valid_precisions) / len(valid_precisions)
        valid_recall = sum(valid_recalls) / len(valid_recalls)
        valid_f1 = sum(valid_f1s) / len(valid_f1s)

        print(f"[ Valid stage2 | {epoch + 1:03d}/{n_epochs:03d} ] loss = {valid_loss:.5f}, acc = {valid_acc:.4f}, precision = {valid_precision:.4f}, recall = {valid_recall:.4f}, f1 = {valid_f1:.4f}")
        with open('output/history/stage2.csv','a') as file:
            file.write(time.strftime("%m-%d %H:%M")+","+f"valid,stage2,{epoch + 1:03d}/{n_epochs:03d},{valid_loss:.5f},{valid_acc:.4f},{valid_precision:.4f},{valid_recall:.4f},{valid_f1:.4f}" + "\n")

        # Record history
        t_loss_list_stage2.append(train_loss)
        t_acc_list_stage2.append(train_acc.cpu())
        v_loss_list_stage2.append(valid_loss)
        v_acc_list_stage2.append(valid_acc.cpu())
        v_f1_list_stage2.append(valid_f1)

        # Param need to be saved according to min loss of val
        if valid_loss == min(v_loss_list_stage2):
            print("Update model save_param !")
            save_param.update({
                'user_review_network' : user_review_network.state_dict(),
                'item_review_network' : item_review_network.state_dict(),
                'co_attention_stage2' : co_attentions.state_dict(),
                'fc_layer_stage2' : fc_layers_stage2.state_dict(),
                'optimizer_stage2': optimizer.state_dict(),
                })

    print("-------------------------- STAGE2 END --------------------------")

    return t_loss_list_stage2, t_acc_list_stage2, v_loss_list_stage2, v_acc_list_stage2, save_param

def draw_loss_curve_stage2(train_loss, valid_loss):
    plt.plot(train_loss, color="mediumblue", label="Train", marker='o')
    plt.plot(valid_loss, color="cornflowerblue", label="Valid", marker='o')
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend(loc="upper right")
    plt.title("Stage2 Loss Curve")
    plt.savefig('output/plot/collab/loss_stage2_{}.png'.format(time.strftime("%m%d%H%M%S")))
    plt.show()

def draw_acc_curve_stage2(train_acc, valid_acc):
    plt.plot(train_acc, color="deeppink", label="Train", marker='o')
    plt.plot(valid_acc, color="pink", label="Valid", marker='o')
    plt.xlabel("Epoch")
    plt.ylabel("Acc")
    plt.legend(loc="upper right")
    plt.title("Stage2 Acc Curve")
    plt.savefig('output/plot/collab/acc_stage2_{}.png'.format(time.strftime("%m%d%H%M%S")))
    plt.show()
